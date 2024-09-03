import asyncio
from collections import defaultdict
from itertools import chain
import json
import traceback
from typing import Mapping, Optional, Sequence, cast

from emcie.common.tools import Tool
from emcie.server.contextual_correlator import ContextualCorrelator
from emcie.server.core.common import generate_id
from emcie.server.logger import Logger

from emcie.server.core.agents import Agent, AgentId, AgentStore
from emcie.server.core.context_variables import (
    ContextVariable,
    ContextVariableStore,
    ContextVariableValue,
)
from emcie.server.core.guideline_connections import ConnectionKind, GuidelineConnectionStore
from emcie.server.core.tools import ToolService
from emcie.server.engines.alpha.message_event_producer import MessageEventProducer
from emcie.server.engines.alpha.guideline_proposer import GuidelineProposer
from emcie.server.engines.alpha.guideline_proposition import GuidelineProposition
from emcie.server.core.guideline_tool_associations import (
    GuidelineToolAssociationStore,
)
from emcie.server.engines.alpha.tool_event_producer import ToolEventProducer
from emcie.server.core.terminology import Term, TerminologyStore
from emcie.server.engines.alpha.utils import context_variables_to_json
from emcie.server.engines.event_emitter import EventEmitter, EmittedEvent
from emcie.server.engines.common import Context, Engine
from emcie.server.core.guidelines import Guideline, GuidelineStore
from emcie.server.core.sessions import (
    Event,
    MessageEventData,
    SessionId,
    SessionStore,
    ToolEventData,
)


class AlphaEngine(Engine):
    def __init__(
        self,
        logger: Logger,
        correlator: ContextualCorrelator,
        agent_store: AgentStore,
        session_store: SessionStore,
        context_variable_store: ContextVariableStore,
        terminology_store: TerminologyStore,
        guideline_store: GuidelineStore,
        guideline_connection_store: GuidelineConnectionStore,
        tool_service: ToolService,
        guideline_tool_association_store: GuidelineToolAssociationStore,
    ) -> None:
        self.logger = logger
        self.correlator = correlator

        self.agent_store = agent_store
        self.session_store = session_store
        self.context_variable_store = context_variable_store
        self.terminology_store = terminology_store
        self.guideline_store = guideline_store
        self.guideline_connection_store = guideline_connection_store
        self.tool_service = tool_service
        self.guideline_tool_association_store = guideline_tool_association_store

        self.max_tool_call_iterations = 5

        self.guideline_proposer = GuidelineProposer(self.logger)
        self.tool_event_producer = ToolEventProducer(
            self.logger,
            self.correlator,
            self.tool_service,
        )
        self.message_event_producer = MessageEventProducer(self.logger, self.correlator)

    async def process(
        self,
        context: Context,
        event_emitter: EventEmitter,
    ) -> bool:
        try:
            with self.correlator.correlation_scope(generate_id()):
                await self._do_process(context, event_emitter)
            return True
        except asyncio.CancelledError:
            return False
        except Exception as exc:
            self.logger.error(f"Processing error: {traceback.format_exception(exc)}")
            raise
        except BaseException as exc:
            self.logger.critical(f"Processing error: {traceback.format_exception(exc)}")
            raise

    async def _do_process(
        self,
        context: Context,
        event_emitter: EventEmitter,
    ) -> None:
        agent = await self.agent_store.read_agent(context.agent_id)
        interaction_history = list(await self.session_store.list_events(context.session_id))
        last_known_event_offset = interaction_history[-1].offset if interaction_history else -1

        await event_emitter.emit_status_event(
            correlation_id=self.correlator.correlation_id,
            data={
                "acknowledged_offset": last_known_event_offset,
                "status": "acknowledged",
                "data": {},
            },
        )

        try:
            context_variables = await self._load_context_variables(
                agent_id=context.agent_id,
                session_id=context.session_id,
            )

            terms = set(
                await self._load_relevant_terms(
                    agents=[agent],
                    context_variables=context_variables,
                    interaction_history=interaction_history,
                )
            )

            await event_emitter.emit_status_event(
                correlation_id=self.correlator.correlation_id,
                data={
                    "acknowledged_offset": last_known_event_offset,
                    "status": "processing",
                    "data": {},
                },
            )

            all_tool_events: list[EmittedEvent] = []
            tool_call_iterations = 0

            while True:
                tool_call_iterations += 1

                (
                    ordinary_guideline_propositions,
                    tool_enabled_guideline_propositions,
                ) = await self._load_guideline_propositions(
                    agents=[agent],
                    context_variables=context_variables,
                    interaction_history=interaction_history,
                    terms=list(terms),
                    staged_events=all_tool_events,
                )

                terms.update(
                    await self._load_relevant_terms(
                        agents=[agent],
                        propositions=list(
                            chain(
                                ordinary_guideline_propositions,
                                tool_enabled_guideline_propositions.keys(),
                            ),
                        ),
                    )
                )
                if tool_events := await self.tool_event_producer.produce_events(
                    session_id=context.session_id,
                    agents=[agent],
                    context_variables=context_variables,
                    interaction_history=interaction_history,
                    terms=list(terms),
                    ordinary_guideline_propositions=ordinary_guideline_propositions,
                    tool_enabled_guideline_propositions=tool_enabled_guideline_propositions,
                    staged_events=all_tool_events,
                ):
                    all_tool_events += tool_events

                    terms.update(
                        set(
                            await self._load_relevant_terms(
                                agents=[agent],
                                staged_events=tool_events,
                            )
                        )
                    )
                else:
                    break

                if tool_call_iterations == self.max_tool_call_iterations:
                    self.logger.warning(
                        f"Reached max tool call iterations ({tool_call_iterations})"
                    )
                    break

            await event_emitter.emit_status_event(
                correlation_id=self.correlator.correlation_id,
                data={
                    "acknowledged_offset": last_known_event_offset,
                    "status": "typing",
                    "data": {},
                },
            )

            message_events = await self.message_event_producer.produce_events(
                agents=[agent],
                context_variables=context_variables,
                interaction_history=interaction_history,
                terms=list(terms),
                ordinary_guideline_propositions=ordinary_guideline_propositions,
                tool_enabled_guideline_propositions=tool_enabled_guideline_propositions,
                staged_events=all_tool_events,
            )

            for e in all_tool_events:
                await event_emitter.emit_tool_event(
                    self.correlator.correlation_id,
                    cast(ToolEventData, e.data),
                )

            for e in message_events:
                await event_emitter.emit_message_event(
                    self.correlator.correlation_id,
                    cast(MessageEventData, e.data),
                )
        except asyncio.CancelledError:
            await event_emitter.emit_status_event(
                correlation_id=self.correlator.correlation_id,
                data={
                    "acknowledged_offset": last_known_event_offset,
                    "status": "cancelled",
                    "data": {},
                },
            )

            raise
        finally:
            await event_emitter.emit_status_event(
                correlation_id=self.correlator.correlation_id,
                data={
                    "acknowledged_offset": last_known_event_offset,
                    "status": "ready",
                    "data": {},
                },
            )

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

    async def _load_guideline_propositions(
        self,
        agents: Sequence[Agent],
        context_variables: Sequence[tuple[ContextVariable, ContextVariableValue]],
        interaction_history: Sequence[Event],
        terms: Sequence[Term],
        staged_events: Sequence[EmittedEvent],
    ) -> tuple[Sequence[GuidelineProposition], Mapping[GuidelineProposition, Sequence[Tool]]]:
        all_relevant_guidelines = await self._fetch_guideline_propositions(
            agents=agents,
            context_variables=context_variables,
            interaction_history=interaction_history,
            staged_events=staged_events,
            terms=terms,
        )

        tool_enabled_guidelines = await self._find_tool_enabled_guidelines_propositions(
            guideline_propositions=all_relevant_guidelines,
        )

        ordinary_guidelines = list(
            set(all_relevant_guidelines).difference(tool_enabled_guidelines),
        )

        return ordinary_guidelines, tool_enabled_guidelines

    async def _fetch_guideline_propositions(
        self,
        agents: Sequence[Agent],
        context_variables: Sequence[tuple[ContextVariable, ContextVariableValue]],
        interaction_history: Sequence[Event],
        terms: Sequence[Term],
        staged_events: Sequence[EmittedEvent],
    ) -> Sequence[GuidelineProposition]:
        assert len(agents) == 1

        all_possible_guidelines = await self.guideline_store.list_guidelines(
            guideline_set=agents[0].id,
        )

        direct_propositions = await self.guideline_proposer.propose_guidelines(
            agents=agents,
            guidelines=list(all_possible_guidelines),
            context_variables=context_variables,
            interaction_history=interaction_history,
            terms=terms,
            staged_events=staged_events,
        )

        inferred_propositions = await self._propose_connected_guidelines(
            guideline_set=agents[0].id,
            propositions=direct_propositions,
        )

        return [*direct_propositions, *inferred_propositions]

    async def _propose_connected_guidelines(
        self,
        guideline_set: str,
        propositions: Sequence[GuidelineProposition],
    ) -> Sequence[GuidelineProposition]:
        connected_guidelines_by_proposition = defaultdict[
            GuidelineProposition, list[tuple[Guideline, ConnectionKind]]
        ](list)

        for proposition in propositions:
            connected_guideline_ids = {
                (c.target, c.kind)
                for c in await self.guideline_connection_store.list_connections(
                    indirect=True,
                    source=proposition.guideline.id,
                )
            }

            for connected_guideline_id, connection_kind in connected_guideline_ids:
                if any(connected_guideline_id == p.guideline.id for p in propositions):
                    # no need to add this connected one as it's already an assumed proposition
                    continue

                connected_guideline = await self.guideline_store.read_guideline(
                    guideline_set=guideline_set,
                    guideline_id=connected_guideline_id,
                )

                connected_guidelines_by_proposition[proposition].append(
                    (connected_guideline, connection_kind),
                )

        proposition_and_inferred_guideline_guideline_pairs: list[
            tuple[GuidelineProposition, Guideline, ConnectionKind]
        ] = []

        for proposition, connected_guidelines in connected_guidelines_by_proposition.items():
            for connected_guideline, connection_kind in connected_guidelines:
                if existing_connections := [
                    connection
                    for connection in proposition_and_inferred_guideline_guideline_pairs
                    if connection[1] == connected_guideline
                ]:
                    assert len(existing_connections) == 1
                    existing_connection = existing_connections[0]

                    # We're basically saying, if this connected guideline is already
                    # connected to a proposition with a higher priority than the proposition
                    # at hand, then we want to keep the associated with the proposition
                    # that has the higher priority, because it will go down as the inferred
                    # priority of our connected guideline's proposition...
                    #
                    # Now try to read that out loud in one go :)
                    if existing_connection[2] == "entails" and connection_kind == "suggests":
                        continue  # Stay with existing one
                    elif existing_connection[0].score >= proposition.score:
                        continue  # Stay with existing one
                    else:
                        # This proposition's score is higher, so it's better that
                        # we associate the connected guideline with this one.
                        # we'll add it soon, but meanwhile let's remove the old one.
                        proposition_and_inferred_guideline_guideline_pairs.remove(
                            existing_connection,
                        )

                proposition_and_inferred_guideline_guideline_pairs.append(
                    (proposition, connected_guideline, connection_kind),
                )

        return [
            GuidelineProposition(
                guideline=connection[1],
                score={
                    "suggests": connection[0].score // 2,
                    "entails": connection[0].score,
                }[connection[2]],
                rationale="Automatically inferred from context",
            )
            for connection in proposition_and_inferred_guideline_guideline_pairs
        ]

    async def _find_tool_enabled_guidelines_propositions(
        self,
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
            tool = await self.tool_service.read_tool(association.tool_id)
            tools_for_guidelines[guideline_propositions_by_id[association.guideline_id]].append(
                tool
            )

        return dict(tools_for_guidelines)

    async def _load_relevant_terms(
        self,
        agents: Sequence[Agent],
        context_variables: Optional[Sequence[tuple[ContextVariable, ContextVariableValue]]] = None,
        interaction_history: Optional[Sequence[Event]] = None,
        propositions: Optional[Sequence[GuidelineProposition]] = None,
        staged_events: Optional[Sequence[EmittedEvent]] = None,
    ) -> Sequence[Term]:
        assert len(agents) == 1

        agent = agents[0]

        context = ""

        if context_variables:
            context += f"\n{context_variables_to_json(context_variables=context_variables)}"

        if interaction_history:
            context += str([e.data for e in interaction_history])

        if propositions:
            context += str(
                [
                    f"When {p.guideline.content.predicate}, then {p.guideline.content.action}"
                    for p in propositions
                ]
            )

        if staged_events:
            context += str([e.data for e in staged_events])

        if context:
            self.logger.debug(
                f"Finding relevant terms for the context: {json.dumps(context, indent=2)}"
            )
            return await self.terminology_store.find_relevant_terms(
                term_set=agent.name,
                query=context,
            )
        return []
