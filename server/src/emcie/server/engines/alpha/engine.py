from typing import Iterable

from emcie.server.core.tools import ToolStore
from emcie.server.engines.alpha.event_producer import EventProducer
from emcie.server.engines.alpha.guideline_filter import GuidelineFilter
from emcie.server.engines.alpha.guideline_tool_association import GuidelineToolAssociationStore
from emcie.server.engines.alpha.utils import (
    divide_guidelines_by_tool_association,
    map_guidelines_to_associated_tools,
)
from emcie.server.engines.common import Context, Engine, ProducedEvent
from emcie.server.core.guidelines import GuidelineStore
from emcie.server.core.sessions import SessionStore


class AlphaEngine(Engine):
    def __init__(
        self,
        session_store: SessionStore,
        guideline_store: GuidelineStore,
        tool_store: ToolStore,
        guideline_tool_association_store: GuidelineToolAssociationStore,
    ) -> None:
        self.session_store = session_store
        self.guideline_store = guideline_store
        self.tool_store = tool_store
        self.guideline_tool_association_store = guideline_tool_association_store

        self.event_producer = EventProducer()
        self.guide_filter = GuidelineFilter()

    async def process(self, context: Context) -> Iterable[ProducedEvent]:
        events = await self.session_store.list_events(
            session_id=context.session_id,
        )

        all_possible_guidelines = await self.guideline_store.list_guidelines(
            guideline_set=context.agent_id,
        )

        all_possible_tools = await self.tool_store.list_tools(
            tool_set=context.agent_id,
        )

        relevant_guideline = await self.guide_filter.find_relevant_guidelines(
            guidelines=all_possible_guidelines,
            interaction_history=events,
        )

        guideline_tool_associations = (
            await self.guideline_tool_association_store.list_associations()
        )

        guidelines_without_tools, guidelines_with_tools = (
            await divide_guidelines_by_tool_association(
                guidelines=relevant_guideline,
                associations=guideline_tool_associations,
            )
        )

        relevant_guidelines_with_tools = await map_guidelines_to_associated_tools(
            tools=all_possible_tools,
            guidelines=guidelines_with_tools,
            associations=guideline_tool_associations,
        )

        return await self.event_producer.produce_events(
            interaction_history=events,
            guidelines_without_tools=guidelines_without_tools,
            guidelines_with_tools=relevant_guidelines_with_tools,
            tools=all_possible_tools,
        )
