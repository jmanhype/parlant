from collections import defaultdict
from typing import Iterable

from emcie.server.core.agents import AgentId
from emcie.server.core.context_variables import (
    ContextVariable,
    ContextVariableStore,
    ContextVariableValue,
)
from emcie.server.core.tools import Tool, ToolStore
from emcie.server.engines.alpha.event_producer import EventProducer
from emcie.server.engines.alpha.guideline_filter import GuidelineFilter, GuidelineProposition
from emcie.server.engines.alpha.guideline_tool_associations import (
    GuidelineToolAssociationStore,
)
from emcie.server.engines.common import Context, Engine, ProducedEvent
from emcie.server.core.guidelines import GuidelineStore
from emcie.server.core.sessions import Event, SessionId, SessionStore


class AlphaEngine(Engine):
    def __init__(
        self,
        session_store: SessionStore,
        context_variable_store: ContextVariableStore,
        guideline_store: GuidelineStore,
        tool_store: ToolStore,
        guideline_tool_association_store: GuidelineToolAssociationStore,
    ) -> None:
        self.session_store = session_store
        self.context_variable_store = context_variable_store
        self.guideline_store = guideline_store
        self.tool_store = tool_store
        self.guideline_tool_association_store = guideline_tool_association_store

        self.event_producer = EventProducer()
        self.guide_filter = GuidelineFilter()

    async def process(self, context: Context) -> Iterable[ProducedEvent]:
        interaction_history = list(await self.session_store.list_events(context.session_id))

        context_variables = await self._load_context_variables(
            agent_id=context.agent_id,
            session_id=context.session_id,
        )

        ordinary_proposed_guidelines, tool_enabled_proposed_guidelines = (
            await self._load_guidelines(
                agent_id=context.agent_id,
                context_variables=context_variables,
                interaction_history=interaction_history,
            )
        )

        return await self.event_producer.produce_events(
            context_variables=context_variables,
            interaction_history=interaction_history,
            ordinary_proposed_guidelines=ordinary_proposed_guidelines,
            tool_enabled_proposed_guidelines=tool_enabled_proposed_guidelines,
        )

    async def _load_context_variables(
        self,
        agent_id: AgentId,
        session_id: SessionId,
    ) -> list[tuple[ContextVariable, ContextVariableValue]]:
        session = await self.session_store.read_session(session_id)

        variables = await self.context_variable_store.list_variables(
            variable_set=agent_id,
        )

        return [
            (
                variable,
                await self.context_variable_store.read_value(
                    variable_set=agent_id,
                    key=session.end_user_id,
                    variable_id=variable.id,
                ),
            )
            for variable in variables
        ]

    async def _load_guidelines(
        self,
        agent_id: AgentId,
        context_variables: list[tuple[ContextVariable, ContextVariableValue]],
        interaction_history: list[Event],
    ) -> tuple[Iterable[GuidelineProposition], dict[GuidelineProposition, Iterable[Tool]]]:
        all_relevant_guidelines = await self._fetch_relevant_guidelines(
            agent_id=agent_id,
            context_variables=context_variables,
            interaction_history=interaction_history,
        )

        tool_enabled_guidelines = await self._find_tool_enabled_guidelines(
            agent_id=agent_id,
            proposed_guidelines=all_relevant_guidelines,
        )

        ordinary_guidelines = all_relevant_guidelines.difference(tool_enabled_guidelines)

        return ordinary_guidelines, tool_enabled_guidelines

    async def _fetch_relevant_guidelines(
        self,
        agent_id: AgentId,
        context_variables: list[tuple[ContextVariable, ContextVariableValue]],
        interaction_history: list[Event],
    ) -> set[GuidelineProposition]:
        all_possible_guidelines = await self.guideline_store.list_guidelines(
            guideline_set=agent_id,
        )

        relevant_guidelines = await self.guide_filter.find_relevant_guidelines(
            guidelines=all_possible_guidelines,
            context_variables=context_variables,
            interaction_history=interaction_history,
        )

        return set(relevant_guidelines)

    async def _find_tool_enabled_guidelines(
        self,
        agent_id: AgentId,
        proposed_guidelines: Iterable[GuidelineProposition],
    ) -> dict[GuidelineProposition, Iterable[Tool]]:
        guideline_tool_associations = list(
            await self.guideline_tool_association_store.list_associations()
        )
        proposed_guidelines_by_id = {r.guideline.id: r for r in proposed_guidelines}

        relevant_associations = [
            a for a in guideline_tool_associations if a.guideline_id in proposed_guidelines_by_id
        ]

        tools_for_guidelines: dict[GuidelineProposition, list[Tool]] = defaultdict(list)

        for association in relevant_associations:
            tool = await self.tool_store.read_tool(agent_id, association.tool_id)
            tools_for_guidelines[proposed_guidelines_by_id[association.guideline_id]].append(tool)

        return dict(tools_for_guidelines)
