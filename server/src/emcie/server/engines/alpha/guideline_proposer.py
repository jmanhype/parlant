import asyncio
import json
import jsonfinder  # type: ignore
from typing import Sequence
from loguru import logger

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
        guidelines: Sequence[Guideline],
        context_variables: Sequence[tuple[ContextVariable, ContextVariableValue]],
        interaction_history: Sequence[Event],
    ) -> Sequence[GuidelineProposition]:
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
        context_variables: list[tuple[ContextVariable, ContextVariableValue]],
        interaction_history: list[Event],
        guidelines: list[Guideline],
    ) -> str:
        builder = PromptBuilder()

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
            """
Process Description
-------------------
a. Examine the provided interaction events to discern
the latest state of interaction between the user and the assistant.
b. Determine the applicability of each predicate based on the most recent interaction state.
    Note: There are exactly {len(guidelines)} predicates.
c. Assign a relevance score to each predicate, from 1 to 10, where 10 denotes high relevance.

Expected Output Description
---------------------------
- Create a JSON object specifying the applicability of each predicate, formatted as follows:

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
[{{"id": "MZC1H9iyYe", "kind": "<message>", "source": "user",
"data": {{"message": "Can I purchase a subscription to your software?"}},
{{"id": "F2oFNx_Ld8", "kind": "<message>", "source": "assistant",
"data": {{"message": "Absolutely, I can assist you with that right now."}},
{{"id": "dfI1jYAjqe", "kind": "<message>", "source": "user",
"data": {{"message": "Please proceed with the subscription for the Pro plan."}},
{{"id": "2ZWfAC4xLf", "kind": "<message>", "source": "assistant",
"data": {{"message": "Your subscription has been successfully activated.
Is there anything else I can help you with?"}},
{{"id": "78oTChjBfM", "kind": "<message>", "source": "user",
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
[{{"id": "P06dNR7ySO", "kind": "<message>", "source": "user",
"data": {{"message": "I need to make this quick.
Can you give me a brief overview of your pricing plans?"}},
{{"id": "bwZwM6YjfR", "kind": "<message>", "source": "assistant",
"data": {{"message": "Absolutely, I'll keep it concise. We have three main plans: Basic,
Advanced, and Pro. Each offers different features, which I can summarize quickly for you."}},
{{"id": "bFKLDMthb2", "kind": "<message>", "source": "user",
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
