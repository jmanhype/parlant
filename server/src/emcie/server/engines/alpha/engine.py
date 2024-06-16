from collections import defaultdict
from itertools import chain
from typing import Iterable

from emcie.server.core.agents import AgentId
from emcie.server.core.tools import Tool, ToolStore
from emcie.server.engines.alpha.event_producer import EventProducer
from emcie.server.engines.alpha.guideline_filter import GuidelineFilter
from emcie.server.engines.alpha.guideline_tool_associations import (
    GuidelineToolAssociationStore,
)
from emcie.server.engines.common import Context, Engine, ProducedEvent
from emcie.server.core.guidelines import Guideline, GuidelineStore
from emcie.server.core.sessions import Event, SessionStore


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
        interaction_history = list(
            await self.session_store.list_events(
                session_id=context.session_id,
            )
        )

        all_relevant_guidelines = await self._fetch_relevant_guidelines(
            agent_id=context.agent_id,
            interaction_history=interaction_history,
        )

        tool_enabled_guidelines = await self._find_tool_enabled_guidelines(
            agent_id=context.agent_id,
            guidelines=all_relevant_guidelines,
        )

        ordinary_guidelines = all_relevant_guidelines.difference(tool_enabled_guidelines)

        enabled_tools = chain(*tool_enabled_guidelines.values())

        return await self.event_producer.produce_events(
            interaction_history=interaction_history,
            ordinary_guidelines=ordinary_guidelines,
            tool_enabled_guidelines=tool_enabled_guidelines,
            tools=enabled_tools,
        )

    async def _fetch_relevant_guidelines(
        self,
        agent_id: AgentId,
        interaction_history: list[Event],
    ) -> set[Guideline]:
        all_possible_guidelines = await self.guideline_store.list_guidelines(
            guideline_set=agent_id,
        )

        relevant_guidelines = await self.guide_filter.find_relevant_guidelines(
            guidelines=all_possible_guidelines,
            interaction_history=interaction_history,
        )

        return set(relevant_guidelines)

    async def _find_tool_enabled_guidelines(
        self,
        agent_id: AgentId,
        guidelines: Iterable[Guideline],
    ) -> dict[Guideline, Iterable[Tool]]:
        guideline_tool_associations = list(
            await self.guideline_tool_association_store.list_associations()
        )
        guidelines_by_id = {g.id: g for g in guidelines}

        relevant_associations = [
            a for a in guideline_tool_associations if a.guideline_id in guidelines_by_id
        ]

        tools_for_guidelines: dict[Guideline, list[Tool]] = defaultdict(list)

        for association in relevant_associations:
            tool = await self.tool_store.read_tool(agent_id, association.tool_id)
            tools_for_guidelines[guidelines_by_id[association.guideline_id]].append(tool)

        return dict(tools_for_guidelines)
