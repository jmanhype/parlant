import asyncio
import json
from typing import Iterable, TypedDict

from emcie.server.engines.alpha.utils import (
    duration_logger,
    events_to_json,
    make_llm_client,
)
from emcie.server.guidelines import Guideline
from emcie.server.sessions import Event


class GuidelineFilter:
    class PredicateCheck(TypedDict):
        guideline: Guideline
        score: int
        rationale: str

    def __init__(self) -> None:
        self._llm_client = make_llm_client("openai")

    async def find_relevant_guidelines(
        self,
        guidelines: Iterable[Guideline],
        interaction_history: Iterable[Event],
    ) -> Iterable[Guideline]:
        guideline_list = list(guidelines)

        if not guideline_list:
            return []

        batches = self._create_batches(guideline_list, batch_size=5)

        with duration_logger(f"Total guideline filtering ({len(batches)} batches)"):
            batch_tasks = [self._process_batch(interaction_history, batch) for batch in batches]
            batch_results = await asyncio.gather(*batch_tasks)
            aggregated_checks = sum(batch_results, [])

        return [c["guideline"] for c in aggregated_checks]

    def _create_batches(
        self,
        guidelines: list[Guideline],
        batch_size: int,
    ) -> list[list[Guideline]]:
        batches = []
        batch_count = int(len(guidelines) / batch_size) + 1

        for batch_number in range(batch_count):
            start_offset = batch_number * batch_size
            end_offset = start_offset + batch_size
            batch = guidelines[start_offset:end_offset]
            batches.append(batch)

        return batches

    async def _process_batch(
        self,
        interaction_history: Iterable[Event],
        batch: list[Guideline],
    ) -> list[PredicateCheck]:
        prompt = self._format_prompt(interaction_history, batch)

        with duration_logger("Guideline batch filtering"):
            llm_response = await self._generate_llm_response(prompt)

        predicate_checks = json.loads(llm_response)["checks"]

        checks_by_index = {(int(c["predicate_number"]) - 1): c for c in predicate_checks}

        relevant_checks_by_index = {
            index: check for index, check in checks_by_index.items() if check["applies_score"] >= 8
        }

        return [
            {
                "guideline": batch[i],
                "score": relevant_checks_by_index[i]["applies_score"],
                "rationale": relevant_checks_by_index[i]["rationale"],
            }
            for i in relevant_checks_by_index.keys()
        ]

    def _format_prompt(
        self,
        interaction_history: Iterable[Event],
        guidelines: list[Guideline],
    ) -> str:
        json_events = events_to_json(interaction_history)
        predicates = "\n".join(f"{i}) {g.predicate}" for i, g in enumerate(guidelines, start=1))

        return f"""\
The following is a list of events describing a back-and-forth
interaction between you, an AI assistant, and a user: ###
{json_events}
###

The following is a list of predicates that may or may not apply
to the LAST KNOWN STATE of the human/assistant interaction given above: ###
{predicates}
###

There are exactly {len(guidelines)} predicate(s).

Your job is to determine which of the {len(guidelines)} predicate(s) applies
to the LAST KNOWN STATE of the human/assistant interaction, and which don't.
You must answer this question for each and every one of the predicate(s) provided.

Produce a JSON object of the following format:

{{ "checks": [
    {{
        "predicate_number": "1",
        "rationale": <A FEW WORDS THAT EXPLAIN WHY IT DOES OR DOESN'T APPLY>",
        "applies_score": <INTEGER FROM 1 TO 10>,
    }},
    ...,
    {{
        "predicate_number": "N",
        "rationale": <A FEW WORDS THAT EXPLAIN WHY IT DOES OR DOESN'T APPLY>",
        "applies_score": <INTEGER FROM 1 TO 10>
    }}
]}}
"""

    async def _generate_llm_response(self, prompt: str) -> str:
        response = await self._llm_client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="gpt-3.5-turbo",
            temperature=0.0,
            response_format={"type": "json_object"},
        )

        return response.choices[0].message.content or ""
