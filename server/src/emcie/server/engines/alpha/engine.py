import json
from textwrap import dedent
from typing import Iterable
from pydantic import BaseModel, Field

from emcie.server.engines.alpha.guide_filter import GuideFilter
from emcie.server.engines.alpha.utils import events_to_json, make_llm_client
from emcie.server.engines.common import Context, Engine, ProducedEvent
from emcie.server.guides import Guide, GuideStore
from emcie.server.sessions import Event, SessionStore


class EventProducer:
    def __init__(
        self,
    ) -> None:
        self._llm_client = make_llm_client()

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
        json_events = events_to_json(interaction_history)
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
        class OutputEvent(BaseModel):
            type: str = Field(
                description="The event type, which is always 'message'",
                default="message",
            )
            data: str = Field(description="Message content")

        response = await self._llm_client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="mistralai/Mistral-7B-Instruct-v0.1",
            response_format={
                "type": "json_object",
                "schema": OutputEvent.model_json_schema(),
            },  # type: ignore
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
