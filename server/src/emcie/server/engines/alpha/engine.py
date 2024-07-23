from collections import defaultdict
from itertools import chain
from typing import Mapping, Sequence
from loguru import logger

from emcie.server.core.agents import Agent, AgentId, AgentStore
from emcie.server.core.context_variables import (
    ContextVariable,
    ContextVariableStore,
    ContextVariableValue,
)
from emcie.server.core.tools import Tool, ToolStore
from emcie.server.engines.alpha.message_event_producer import MessageEventProducer
from emcie.server.engines.alpha.guideline_proposer import GuidelineProposer
from emcie.server.engines.alpha.guideline_proposition import GuidelineProposition
from emcie.server.engines.alpha.guideline_tool_associations import (
    GuidelineToolAssociationStore,
)
from emcie.server.engines.alpha.tool_event_producer import ToolEventProducer
from emcie.server.engines.common import Context, Engine, ProducedEvent
from emcie.server.core.guidelines import GuidelineStore
from emcie.server.core.sessions import Event, SessionId, SessionStore


class AlphaEngine(Engine):
    def __init__(
        self,
        agent_store: AgentStore,
        session_store: SessionStore,
        context_variable_store: ContextVariableStore,
        guideline_store: GuidelineStore,
        tool_store: ToolStore,
        guideline_tool_association_store: GuidelineToolAssociationStore,
    ) -> None:
        self.agent_store = agent_store
        self.session_store = session_store
        self.context_variable_store = context_variable_store
        self.guideline_store = guideline_store
        self.tool_store = tool_store
        self.guideline_tool_association_store = guideline_tool_association_store

        self.max_tool_call_iterations = 5

        self.guideline_proposer = GuidelineProposer()
        self.tool_event_producer = ToolEventProducer()
        self.message_event_producer = MessageEventProducer()

    async def process(self, context: Context) -> Sequence[ProducedEvent]:
        agent = await self.agent_store.read_agent(context.agent_id)
        interaction_history = list(await self.session_store.list_events(context.session_id))

        context_variables = await self._load_context_variables(
            agent_id=context.agent_id,
            session_id=context.session_id,
        )

        all_tool_events: list[ProducedEvent] = []
        tool_call_iterations = 0

        while True:
            tool_call_iterations += 1

            ordinary_guideline_propositions, tool_enabled_guideline_propositions = (
                await self._load_guidelines(
                    agents=[agent],
                    agent_id=context.agent_id,
                    context_variables=context_variables,
                    interaction_history=interaction_history,
                    staged_events=all_tool_events,
                )
            )

            if tool_events := await self.tool_event_producer.produce_events(
                agents=[agent],
                context_variables=context_variables,
                interaction_history=interaction_history,
                ordinary_guideline_propositions=ordinary_guideline_propositions,
                tool_enabled_guideline_propositions=tool_enabled_guideline_propositions,
                staged_events=all_tool_events,
            ):
                all_tool_events += tool_events
            else:
                break

            if tool_call_iterations == self.max_tool_call_iterations:
                logger.warning(f"Reached max tool call iterations ({tool_call_iterations})")
                break

        message_events = await self.message_event_producer.produce_events(
            agents=[agent],
            context_variables=context_variables,
            interaction_history=interaction_history,
            ordinary_guideline_propositions=ordinary_guideline_propositions,
            tool_enabled_guideline_propositions=tool_enabled_guideline_propositions,
            staged_events=tool_events,
        )

        return list(chain(tool_events, message_events))

    async def _load_context_variables(
        self,
        agent_id: AgentId,
        session_id: SessionId,
    ) -> Sequence[tuple[ContextVariable, ContextVariableValue]]:
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
        agents: Sequence[Agent],
        agent_id: AgentId,
        context_variables: Sequence[tuple[ContextVariable, ContextVariableValue]],
        interaction_history: Sequence[Event],
        staged_events: Sequence[ProducedEvent],
    ) -> tuple[Sequence[GuidelineProposition], Mapping[GuidelineProposition, Sequence[Tool]]]:
        assert len(agents) == 1

        all_relevant_guidelines = await self._fetch_relevant_guidelines(
            agents=agents,
            agent_id=agent_id,
            context_variables=context_variables,
            interaction_history=interaction_history,
            staged_events=staged_events,
        )

        tool_enabled_guidelines = await self._find_tool_enabled_guidelines(
            agent_id=agent_id,
            guideline_propositions=all_relevant_guidelines,
        )

        ordinary_guidelines = list(
            set(all_relevant_guidelines).difference(tool_enabled_guidelines),
        )

        return ordinary_guidelines, tool_enabled_guidelines

    async def _fetch_relevant_guidelines(
        self,
        agents: Sequence[Agent],
        agent_id: AgentId,
        context_variables: Sequence[tuple[ContextVariable, ContextVariableValue]],
        interaction_history: Sequence[Event],
        staged_events: Sequence[ProducedEvent],
    ) -> Sequence[GuidelineProposition]:
        assert len(agents) == 1

        all_possible_guidelines = await self.guideline_store.list_guidelines(
            guideline_set=agent_id,
        )

        relevant_guidelines = await self.guideline_proposer.propose_guidelines(
            agents=agents,
            guidelines=list(all_possible_guidelines),
            context_variables=context_variables,
            interaction_history=interaction_history,
            staged_events=staged_events,
        )

        return relevant_guidelines

    async def _find_tool_enabled_guidelines(
        self,
        agent_id: AgentId,
        guideline_propositions: Sequence[GuidelineProposition],
    ) -> Mapping[GuidelineProposition, Sequence[Tool]]:
        guideline_tool_associations = list(
            await self.guideline_tool_association_store.list_associations()
        )
        guideline_propositions_by_id = {p.guideline.id: p for p in guideline_propositions}

        relevant_associations = [
            a for a in guideline_tool_associations if a.guideline_id in guideline_propositions_by_id
        ]

        tools_for_guidelines: dict[GuidelineProposition, list[Tool]] = defaultdict(list)

        for association in relevant_associations:
            tool = await self.tool_store.read_tool(association.tool_id)
            tools_for_guidelines[guideline_propositions_by_id[association.guideline_id]].append(
                tool
            )

        return dict(tools_for_guidelines)
