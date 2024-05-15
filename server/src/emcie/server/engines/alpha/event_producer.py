import json
from typing import Iterable
from loguru import logger

from emcie.server.engines.alpha.utils import events_to_json, make_llm_client
from emcie.server.engines.common import ProducedEvent
from emcie.server.guidelines import Guideline
from emcie.server.sessions import Event


class EventProducer:
    def __init__(
        self,
    ) -> None:
        self._llm_client = make_llm_client("openai")

    async def produce_events(
        self,
        interaction_history: Iterable[Event],
        guidelines: Iterable[Guideline],
    ) -> Iterable[ProducedEvent]:
        prompt = self._format_prompt(
            interaction_history=interaction_history,
            guidelines=guidelines,
        )

        response_message = await self._generate_response_message(prompt)

        return [
            ProducedEvent(
                source="server",
                type=Event.MESSAGE_TYPE,
                data={"message": response_message},
            )
        ]

    def _format_prompt(
        self,
        interaction_history: Iterable[Event],
        guidelines: Iterable[Guideline],
    ) -> str:
        json_events = events_to_json(interaction_history)
        rules = "\n".join(
            f"{i}) When {g.predicate}, then {g.content}" for i, g in enumerate(guidelines, start=1)
        )

        return f"""\
The following is a list of events describing a back-and-forth
interaction between you, an AI assistant, and a user: ###
{json_events}
###

You must generate your response message to the current
(latest) state of the interaction.

In generating the response, you must adhere to the following rules: ###
{rules}
###

Propose revisions to the message content until you are
absolutely sure that your proposed message adheres to
each and every one of the provided instructions,
with regards to the interaction's latest state.
Check yourself and criticize the last revision
every time, until you are sure the message
follows all of the instructions.

Produce a valid JSON object in the format according to the following example.

{{
    "revisions": [
        {{
            "content": "some proposed message content",
            "rules_followed": [
                "#1; correctly did...",
                "#3; correctly said..."
            ],
            "rules_broken": [
                "#5; didn't do...",
                "#2; didn't say..."
            ],
            "followed_all_rules": false
        }},
        ...,
        {{
            "content": "final verified message content",
            "rules_followed": [
                "#1; correctly did...",
                "#2; correctly said...",
                "#3; correctly said...",
                "#5; correctly did..."
            ],
            "rules_broken": [],
            "followed_all_rules": true
        }},
    ]
}}
"""

    async def _generate_response_message(self, prompt: str) -> str:
        response = await self._llm_client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="gpt-4o",
            response_format={"type": "json_object"},
            temperature=0.5,
        )

        content = response.choices[0].message.content or ""

        json_content = json.loads(content)

        final_revision = json_content["revisions"][-1]

        if not final_revision["followed_all_rules"]:
            logger.warning(f"PROBLEMATIC RESPONSE: {content}")

        return str(final_revision["content"])
