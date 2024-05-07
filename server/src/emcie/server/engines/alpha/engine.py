import json
import os
from textwrap import dedent
from typing import Any, Iterable
from openai import AsyncClient

from emcie.server.engines.common import Context, Engine, ProducedEvent
from emcie.server.guides import Guide, GuideStore
from emcie.server.sessions import Event, SessionStore


class EventProducer:
    def __init__(
        self,
    ) -> None:
        self._llm_client = AsyncClient(api_key=os.environ["OPENAI_API_KEY"])

    async def produce_events(
        self,
        input_events: Iterable[Event],
        guides: Iterable[Guide],
    ) -> Iterable[ProducedEvent]:
        prompt = self._format_prompt(
            input_events=input_events,
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

    def _events_to_json(self, events: Iterable[Event]) -> str:
        event_dicts = [self._event_to_dict(e) for e in events]
        return json.dumps(event_dicts)

    def _format_prompt(
        self,
        input_events: Iterable[Event],
        guides: Iterable[Guide],
    ) -> str:
        json_events = self._events_to_json(input_events)
        instructions = "\n".join(
            f"{i}) {g.predicate}, {g.content}" for i, g in enumerate(guides, start=1)
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

    def _event_to_dict(self, event: Event) -> dict[str, Any]:
        return {
            "id": event.id,
            "type": event.type,
            "source": {
                "client": "user",
                "server": "assistant",
            }.get(event.source),
            "data": event.data,
        }


class AlphaEngine(Engine):
    def __init__(
        self,
        session_store: SessionStore,
        guide_store: GuideStore,
    ) -> None:
        self.session_store = session_store
        self.guide_store = guide_store
        self.event_producer = EventProducer()

    async def process(self, context: Context) -> Iterable[ProducedEvent]:
        events = await self.session_store.list_events(
            session_id=context.session_id,
        )

        guides = await self.guide_store.list_guides(
            guide_set=context.agent_id,
        )

        return await self.event_producer.produce_events(
            events,
            guides,
        )
