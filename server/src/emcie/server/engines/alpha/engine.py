import json
import os
from textwrap import dedent
from typing import Any, Iterable
from openai import AsyncClient

from emcie.server.engines.common import Context, Engine, ProducedEvent
from emcie.server.guides import Guide, GuideStore
from emcie.server.sessions import Event, SessionStore


def _make_llm_client() -> AsyncClient:
    return AsyncClient(api_key=os.environ["OPENAI_API_KEY"])


def _events_to_json(events: Iterable[Event]) -> str:
    event_dicts = [_event_to_dict(e) for e in events]
    return json.dumps(event_dicts)


def _event_to_dict(event: Event) -> dict[str, Any]:
    return {
        "id": event.id,
        "type": event.type,
        "source": {
            "client": "user",
            "server": "assistant",
        }.get(event.source),
        "data": event.data,
    }


class EventProducer:
    def __init__(
        self,
    ) -> None:
        self._llm_client = _make_llm_client()

    async def produce_events(
        self,
        interaction_history: Iterable[Event],
        guides: Iterable[Guide],
    ) -> Iterable[ProducedEvent]:
        prompt = self._format_prompt(
            interaction_history=interaction_history,
            guides=guides,
        )

        llm_response = await self._generate_llm_response(prompt)
        output_event = json.loads(llm_response)

        return [
            ProducedEvent(
                source="server",
                type=Event.MESSAGE_TYPE,
                data={"message": output_event["data"]},
            )
        ]

    def _format_prompt(
        self,
        interaction_history: Iterable[Event],
        guides: Iterable[Guide],
    ) -> str:
        json_events = _events_to_json(interaction_history)
        instructions = "\n".join(
            f"{i}) When {g.predicate}, then {g.content}" for i, g in enumerate(guides, start=1)
        )

        return dedent(
            f"""\
                The following is a list of events describing a back-and-forth
                interaction between you, an AI assistant, and a user: ###
                {json_events}
                ###

                Please generate the next event in the sequence,
                initiated by you, the AI assistant.

                In generating the next event, you must adhere to
                the following instructions: ###
                {instructions}
                ###

                Produce a JSON object of the following format:

                {{
                    "type": "message",
                    "data": "<MESSAGE CONTENT>"
                }}
            """
        )

    async def _generate_llm_response(self, prompt: str) -> str:
        response = await self._llm_client.chat.completions.create(
            messages=[{"role": "system", "content": prompt}],
            model="gpt-4-0125-preview",
            response_format={"type": "json_object"},
        )

        return response.choices[0].message.content or ""


class GuideFilter:
    def __init__(self) -> None:
        self._llm_client = _make_llm_client()

    async def find_relevant_guides(
        self,
        guides: Iterable[Guide],
        interaction_history: Iterable[Event],
    ) -> Iterable[Guide]:
        guide_list = list(guides)
        prompt = self._format_prompt(interaction_history, guide_list)
        llm_response = await self._generate_llm_response(prompt)
        predicate_checks = json.loads(llm_response)["checks"]
        relevant_predicate_indices = [
            int(p["predicate_number"]) - 1 for p in predicate_checks if p["applies"]
        ]
        relevant_guides = [guide_list[i] for i in relevant_predicate_indices]
        return relevant_guides

    def _format_prompt(
        self,
        interaction_history: Iterable[Event],
        guides: list[Guide],
    ) -> str:
        json_events = _events_to_json(interaction_history)
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
                        "applies": <BOOLEAN>,
                        "rationale": <A FEW WORDS THAT EXPLAIN WHY IT DOES OR DOESN'T APPLY>",
                    }},
                    ...,
                    {{
                        "predicate_number": "N",
                        "applies": <BOOLEAN>,
                        "rationale": <A FEW WORDS THAT EXPLAIN WHY IT DOES OR DOESN'T APPLY>",
                    }}
                ]}}
            """
        )

    async def _generate_llm_response(self, prompt: str) -> str:
        response = await self._llm_client.chat.completions.create(
            messages=[{"role": "system", "content": prompt}],
            model="gpt-4-0125-preview",
            temperature=0.0,
            response_format={"type": "json_object"},
        )

        return response.choices[0].message.content or ""


class AlphaEngine(Engine):
    def __init__(
        self,
        session_store: SessionStore,
        guide_store: GuideStore,
    ) -> None:
        self.session_store = session_store
        self.guide_store = guide_store
        self.event_producer = EventProducer()
        self.guide_filter = GuideFilter()

    async def process(self, context: Context) -> Iterable[ProducedEvent]:
        events = await self.session_store.list_events(
            session_id=context.session_id,
        )

        all_possible_guides = await self.guide_store.list_guides(
            guide_set=context.agent_id,
        )

        relevant_guides = await self.guide_filter.find_relevant_guides(
            guides=all_possible_guides,
            interaction_history=events,
        )

        return await self.event_producer.produce_events(
            interaction_history=events,
            guides=relevant_guides,
        )
