import asyncio
import json
import jsonfinder  # type: ignore
from typing import Sequence
from loguru import logger

from emcie.server.core.agents import Agent
from emcie.server.core.context_variables import ContextVariable, ContextVariableValue
from emcie.server.engines.alpha.guideline_proposition import GuidelineProposition
from emcie.server.engines.alpha.prompt_builder import PromptBuilder
from emcie.server.engines.alpha.utils import (
    duration_logger,
    make_llm_client,
)
from emcie.server.core.guidelines import Guideline
from emcie.server.core.sessions import Event


class GuidelineProposer:
    def __init__(self) -> None:
        self._llm_client = make_llm_client("openai")

    async def propose_guidelines(
        self,
        agents: Sequence[Agent],
        guidelines: Sequence[Guideline],
        context_variables: Sequence[tuple[ContextVariable, ContextVariableValue]],
        interaction_history: Sequence[Event],
    ) -> Sequence[GuidelineProposition]:
        if not guidelines:
            return []

        batches = self._create_batches(guidelines, batch_size=5)

        with duration_logger(f"Total guideline filtering ({len(batches)} batches)"):
            batch_tasks = [
                self._process_batch(
                    agents,
                    context_variables,
                    interaction_history,
                    batch,
                )
                for batch in batches
            ]
            batch_results = await asyncio.gather(*batch_tasks)
            propositions = sum(batch_results, [])

        return propositions

    def _create_batches(
        self,
        guidelines: Sequence[Guideline],
        batch_size: int,
    ) -> Sequence[Sequence[Guideline]]:
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
        agents: Sequence[Agent],
        context_variables: Sequence[tuple[ContextVariable, ContextVariableValue]],
        interaction_history: Sequence[Event],
        batch: Sequence[Guideline],
    ) -> list[GuidelineProposition]:
        prompt = self._format_prompt(
            agents,
            context_variables=context_variables,
            interaction_history=interaction_history,
            guidelines=batch,
        )

        with duration_logger("Guideline batch filtering"):
            llm_response = await self._generate_llm_response(prompt)

        propositions_json = json.loads(llm_response)["checks"]

        logger.debug(f"Guideline filter batch result: {propositions_json}")

        propositions = [
            GuidelineProposition(
                guideline=batch[int(p["predicate_number"]) - 1],
                score=p["applies_score"],
                rationale=p["rationale"],
            )
            for p in propositions_json
            if p["applies_score"] >= 7
        ]

        return propositions

    def _format_prompt(
        self,
        agents: Sequence[Agent],
        context_variables: Sequence[tuple[ContextVariable, ContextVariableValue]],
        interaction_history: Sequence[Event],
        guidelines: Sequence[Guideline],
    ) -> str:
        assert len(agents) == 1
        result_structure = [
            {
                "predicate_number": i,
                "rationale": "<EXPLANATION WHY THE PREDICATE IS RELEVANT OR IRRELEVANT FOR THE "
                "CURRENT STATE OF THE INTERACTION>",
                "applies_score": "<RELEVANCE SCORE>",
            }
            for i, g in enumerate(guidelines, start=1)
        ]

        builder = PromptBuilder()

        builder.add_agent_identity(agents[0])
        builder.add_interaction_history(interaction_history)
        builder.add_context_variables(context_variables)

        builder.add_section(
            """
Task Description
----------------
Your job is to assess the relevance and/or applicability of the provided predicates
to the last known state of an interaction between yourself, AI assistant, and a user.
"""
        )

        builder.add_guideline_predicates(guidelines)

        builder.add_section(
            f"""
IMPORTANT: Please note there are exactly {len(guidelines)} predicates in the list for you to check.

Process Description
-------------------
a. Examine the provided interaction events to discern the latest state of interaction between the user and the assistant.
b. Evaluate the entire interaction to determine if each predicate is still relevant to the most recent interaction state. 
c. If the predicate has already been addressed, assess its continued applicability.
d. Assign an applicability score to each predicate between 1 and 10, where 10 denotes the highest applicability score.

### Examples of Predicate Evaluations:

#### Example #1:
- Interaction Events: ###
[{{"id": "11", "kind": "<message>", "source": "user",
"data": {{"message": "Can I purchase a subscription to your software?"}}}},
{{"id": "23", "kind": "<message>", "source": "assistant",
"data": {{"message": "Absolutely, I can assist you with that right now."}}}},
{{"id": "34", "kind": "<message>", "source": "user",
"data": {{"message": "Please proceed with the subscription for the Pro plan."}}}},
{{"id": "56", "kind": "<message>", "source": "assistant",
"data": {{"message": "Your subscription has been successfully activated.
Is there anything else I can help you with?"}}}},
{{"id": "78", "kind": "<message>", "source": "user",
"data": {{"message": "Yes, can you tell me more about your data security policies?"}}}}]
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
        "rationale": "The purchase-related guideline is irrelevant since the client completed the purchase and the conversation has moved to a new topic.",
        "applies_score": 3
    }},
    {{
        "predicate_number": "2",
        "rationale": "The client specifically inquired about data security policies, making this guideline highly relevant to the ongoing discussion.",
        "applies_score": 9
    }}
]}}
```

#### Example #2:
[{{"id": "112", "kind": "<message>", "source": "user",
"data": {{"message": "I need to make this quick.
Can you give me a brief overview of your pricing plans?"}}}},
{{"id": "223", "kind": "<message>", "source": "assistant",
"data": {{"message": "Absolutely, I'll keep it concise. We have three main plans: Basic,
Advanced, and Pro. Each offers different features, which I can summarize quickly for you."}}}},
{{"id": "334", "kind": "<message>", "source": "user",
"data": {{"message": "Tell me about the Pro plan."}}}},
###
- Predicates: ###
1) the client indicates they are in a hurry
2) a client inquires about pricing plans
3) a client asks for a summary of the features of the three plans.
###
- **Expected Result**:
```json
{{
    "checks": [
        {{
            "predicate_number": "1",
            "rationale": "The client initially stated they were in a hurry. This urgency applies throughout the conversation unless stated otherwise.",
            "applies_score": 8
        }},
        {{
            "predicate_number": "2",
            "rationale": "The client inquired about pricing plans, specifically asking for details about the Pro plan.",
            "applies_score": 9
        }},
        {{
            "predicate_number": "3",
            "rationale": "The plan summarization guideline is irrelevant since the client only asked about the Pro plan.",
            "applies_score": 2
        }},
    ]
}}
```

Expected Output
---------------------------
- Specify the applicability of each predicate by filling in the rationale and applied score in the following list:

    ```json
    {{
        "checks":
        {result_structure}
    }}
    ```
"""  # noqa
        )

        return builder.build()

    async def _generate_llm_response(self, prompt: str) -> str:
        response = await self._llm_client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="gpt-4o",
            temperature=0.3,
            response_format={"type": "json_object"},
        )

        content = response.choices[0].message.content or "{}"
        return json.dumps(jsonfinder.only_json(content)[2])  # type: ignore
