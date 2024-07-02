import asyncio
from dataclasses import dataclass
import json
import jsonfinder  # type: ignore
from typing import Iterable
from loguru import logger

from emcie.server.core.context_variables import ContextVariable, ContextVariableValue
from emcie.server.engines.alpha.utils import (
    context_variables_to_json,
    duration_logger,
    events_to_json,
    make_llm_client,
)
from emcie.server.core.guidelines import Guideline
from emcie.server.core.sessions import Event


@dataclass(frozen=True)
class GuidelineProposition:
    guideline: Guideline
    score: int
    rationale: str


class GuidelineProposer:
    def __init__(self) -> None:
        self._llm_client = make_llm_client("openai")

    async def propose_guidelines(
        self,
        guidelines: Iterable[Guideline],
        context_variables: Iterable[tuple[ContextVariable, ContextVariableValue]],
        interaction_history: Iterable[Event],
    ) -> Iterable[GuidelineProposition]:
        guideline_list = list(guidelines)

        if not guideline_list:
            return []

        batches = self._create_batches(guideline_list, batch_size=5)

        with duration_logger(f"Total guideline filtering ({len(batches)} batches)"):
            batch_tasks = [
                self._process_batch(
                    list(context_variables),
                    list(interaction_history),
                    batch,
                )
                for batch in batches
            ]
            batch_results = await asyncio.gather(*batch_tasks)
            propositions = sum(batch_results, [])

        return propositions

    def _create_batches(
        self,
        guidelines: list[Guideline],
        batch_size: int,
    ) -> list[list[Guideline]]:
        batches = []
        batch_count = len(guidelines) // batch_size + 1

        for batch_number in range(batch_count):
            start_offset = batch_number * batch_size
            end_offset = start_offset + batch_size
            batch = guidelines[start_offset:end_offset]
            batches.append(batch)

        return batches

    async def _process_batch(
        self,
        context_variables: list[tuple[ContextVariable, ContextVariableValue]],
        interaction_history: list[Event],
        batch: list[Guideline],
    ) -> list[GuidelineProposition]:
        prompt = self._format_prompt(
            context_variables=context_variables,
            interaction_history=interaction_history,
            guidelines=batch,
        )

        with duration_logger("Guideline batch filtering"):
            llm_response = await self._generate_llm_response(prompt)

        guideline_propositions_json = json.loads(llm_response)["checks"]

        logger.debug(f"Guideline filter batch result: {guideline_propositions_json}")
        guideline_propositions = [
            GuidelineProposition(
                guideline=batch[int(r["predicate_number"]) - 1],
                score=r["applies_score"],
                rationale=r["rationale"],
            )
            for r in guideline_propositions_json
            if r["applies_score"] >= 8
        ]

        return guideline_propositions

    def _format_prompt(
        self,
        context_variables: list[tuple[ContextVariable, ContextVariableValue]],
        interaction_history: list[Event],
        guidelines: list[Guideline],
    ) -> str:
        json_events = events_to_json(interaction_history)
        context_values = context_variables_to_json(context_variables)
        predicates = "\n".join(f"{i}) {g.predicate}" for i, g in enumerate(guidelines, start=1))
        prompt = """
### Definition of Predicate Relevance Evaluation:
This process involves assessing the relevance of predefined predicates 
to the last known state of an interaction between an AI assistant and a user.

**Objective**: Determine the applicability of each predicate to the latest 
state based on a stream of events.

**Task Description**:
1. **Input**:
"""

        if interaction_history:
            prompt += f"""\
    The following is a list of events describing a back-and-forth
    interaction between you, an AI assistant, and a user: ###
    {json_events}
    ###
    """
        else:
            prompt += """\
    You, an AI assistant, are now present in an online interaction session with a user.
    The session has just started, 
    and the user hasn't said anything yet nor chosen to engage with you.
    """

        if context_variables:
            prompt += f"""
    The following is additional information available 
    about the user and the context of the interaction: ###
    {context_values}
    ###
    """

        prompt += f"""
    - Predicate List: ###
    {predicates}
    ###

2. **Process**:
   a. Examine the provided interaction events to discern 
   the latest state of interaction between the user and the assistant.
   b. Determine the applicability of each predicate based on the most recent interaction state.
      Note: There are exactly {len(guidelines)} predicates.
   c. Assign a relevance score to each predicate, from 1 to 10, where 10 denotes high relevance.

3. **Output**:
   - Create a JSON object summarizing relevance for each predicate, formatted as follows:

    ```json
    {{
        "checks": [
            {{
                "predicate_number": "1",
                "rationale": "<EXPLANATION WHY THE PREDICATE IS RELEVANT OR IRRELEVANT FOR THE CURRENT STATE OF THE INTERACTION>",
                "applies_score": <RELEVANCE SCORE>,
            }},
            ...
            {{
                "predicate_number": "N",
                "rationale": "<EXPLANATION WHY THE PREDICATE IS RELEVANT OR IRRELEVANT FOR THE CURRENT STATE OF THE INTERACTION>",
                "applies_score": <RELEVANCE SCORE>
            }}
        ]
    }}
    ```

### Examples of Predicate Evaluations:

    #### Example #1:
    - Interaction Events: ###
    [{{"id": "MZC1H9iyYe", "type": "<message>", "source": "user", 
    "data": {{"message": "Can I purchase a subscription to your software?"}},
    {{"id": "F2oFNx_Ld8", "type": "<message>", "source": "assistant", 
    "data": {{"message": "Absolutely, I can assist you with that right now."}},
    {{"id": "dfI1jYAjqe", "type": "<message>", "source": "user",
    "data": {{"message": "Please proceed with the subscription for the Pro plan."}},
    {{"id": "2ZWfAC4xLf", "type": "<message>", "source": "assistant",
    "data": {{"message": "Your subscription has been successfully activated. 
    Is there anything else I can help you with?"}},
    {{"id": "78oTChjBfM", "type": "<message>", "source": "user",
    "data": {{"message": "Yes, can you tell me more about your data security policies?"}}]
    ###
    - Predicates: ###
    1) the client initiates a purchase
    2) the client asks about data security
    ###
    - **Expected Result**:
    ```json
    {{ "checks": [
        {{
            "predicate_number": "1",
            "rationale": "The client completed the purchase and 
            the conversation shifted to a new topic,
            making the purchase-related guideline irrelevant.",
            "applies_score": 3
        }},
        {{
            "predicate_number": "2",
            "rationale": "The client specifically inquired about data security policies, 
            making this guideline highly relevant to the ongoing discussion.",
            "applies_score": 10
        }}
    ]}}
    ```

    #### Example #2:
    [{{"id": "P06dNR7ySO", "type": "<message>", "source": "user",
    "data": {{"message": "I need to make this quick.
    Can you give me a brief overview of your pricing plans?"}},
    {{"id": "bwZwM6YjfR", "type": "<message>", "source": "assistant",
    "data": {{"message": "Absolutely, I'll keep it concise. We have three main plans: Basic,
    Advanced, and Pro. Each offers different features, which I can summarize quickly for you."}},
    {{"id": "bFKLDMthb2", "type": "<message>", "source": "user",
    "data": {{"message": "Tell me about the Pro plan."}},
    ###
    - Predicates: ###
    1) the client indicates they are in a hurry
    2) a client inquires about pricing plans
    ###
    - **Expected Result**:
    ```json
    {{
        "checks": [
            {{
                "predicate_number": "1",
                "rationale": "The client initially stated they were in a hurry. "
                "This urgency applies throughout the conversation unless stated otherwise.",
                "applies_score": 8
            }},
            {{
                "predicate_number": "2",
                "rationale": "The client inquired about pricing plans, "
                "specifically asking for details about the Pro plan.",
                "applies_score": 10
            }},
        ]
    }}
    ```
"""  # noqa
        return prompt

    async def _generate_llm_response(self, prompt: str) -> str:
        response = await self._llm_client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="gpt-4o",
            temperature=0.3,
            response_format={"type": "json_object"},
        )

        content = response.choices[0].message.content or "{}"
        return json.dumps(jsonfinder.only_json(content)[2])  # type: ignore
