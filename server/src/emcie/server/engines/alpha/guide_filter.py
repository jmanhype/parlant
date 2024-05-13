import json
from textwrap import dedent
from typing import Iterable
from pydantic import BaseModel, Field

from emcie.server.engines.alpha.utils import events_to_json, make_llm_client
from emcie.server.guides import Guide
from emcie.server.sessions import Event


class GuideFilter:
    def __init__(self) -> None:
        self._llm_client = make_llm_client("together")

    async def find_relevant_guides(
        self,
        guides: Iterable[Guide],
        interaction_history: Iterable[Event],
    ) -> Iterable[Guide]:
        guide_list = list(guides)

        if not guide_list:
            return []

        prompt = self._format_prompt(interaction_history, guide_list)
        llm_response = await self._generate_llm_response(prompt)
        predicate_checks = json.loads(llm_response)["checks"]

        relevant_predicate_indices = [
            int(p["predicate_number"]) - 1 for p in predicate_checks if p["applies_score"] > 6
        ]

        relevant_guides = [guide_list[i] for i in relevant_predicate_indices]

        return relevant_guides

    def _format_prompt(
        self,
        interaction_history: Iterable[Event],
        guides: list[Guide],
    ) -> str:
        json_events = events_to_json(interaction_history)
        predicates = "\n".join(f"{i}) {g.predicate}" for i, g in enumerate(guides, start=1))

        return dedent(
            f"""\
                The following is a list of events describing a back-and-forth
                interaction between you, an AI assistant, and a user: ###
                {json_events}
                ###

                The following is a list of predicates that may or may not apply
                to the LAST KNOWN STATE of the human/assistant interaction given above: ###
                {predicates}
                ###

                There are exactly {len(guides)} predicate(s).

                Your job is to determine which of the {len(guides)} predicate(s) applies
                to the LAST KNOWN STATE of the human/assistant interaction, and which don't.
                You must answer this question for each and every one of the predicate(s) provided.

                Produce a JSON object of the following format:

                {{ "checks": [
                    {{
                        "predicate_number": "1",
                        "applies_score": <INTEGER FROM 1 TO 10>,
                        "rationale": <A FEW WORDS THAT EXPLAIN WHY IT DOES OR DOESN'T APPLY>",
                    }},
                    ...,
                    {{
                        "predicate_number": "N",
                        "applies_score": <INTEGER FROM 1 TO 10>
                        "rationale": <A FEW WORDS THAT EXPLAIN WHY IT DOES OR DOESN'T APPLY>",
                    }}
                ]}}
            """
        )

    async def _generate_llm_response(self, prompt: str) -> str:
        class PredicateCheck(BaseModel):
            predicate_number: int = Field(description="the serial number of the predicate")
            applies_score: int = Field(
                description="A score from 1 to 10 indicating to what extent the predicate"
                "applies to the LATEST STATE of the interaction, "
                "where 1 means 'does not apply' and 10 means 'absolutely applies'"
            )
            rationale: str = Field(
                description="A few words that explain why it does or doesn't apply"
            )

        class PredicateChecks(BaseModel):
            checks: list[PredicateCheck] = Field(
                description="The list of checks, one for each of the provided predicates"
            )

        response = await self._llm_client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="mistralai/Mistral-7B-Instruct-v0.1",
            temperature=0.0,
            response_format={
                "type": "json_object",
                "schema": PredicateChecks.model_json_schema(),
            },  # type: ignore
        )

        return response.choices[0].message.content or ""
