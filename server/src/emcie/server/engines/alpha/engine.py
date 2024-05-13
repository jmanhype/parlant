from typing import Iterable

from emcie.server.engines.alpha.event_producer import EventProducer
from emcie.server.engines.alpha.guide_filter import GuideFilter
from emcie.server.engines.common import Context, Engine, ProducedEvent
from emcie.server.guides import GuideStore
from emcie.server.sessions import SessionStore


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
