from typing import Mapping, Optional, Sequence

from parlant.core.end_users import EndUser, EndUserTag
from parlant.core.engines.alpha.event_generation import EventGenerationResult
from parlant.core.tools import ToolContext
from parlant.core.contextual_correlator import ContextualCorrelator
from parlant.core.nlp.generation import SchematicGenerator
from parlant.core.logging import Logger
from parlant.core.agents import Agent
from parlant.core.context_variables import ContextVariable, ContextVariableValue
from parlant.core.services.tools.service_registry import ServiceRegistry
from parlant.core.sessions import Event, SessionId, ToolEventData
from parlant.core.engines.alpha.guideline_proposition import GuidelineProposition
from parlant.core.glossary import Term
from parlant.core.engines.alpha.tool_caller import ToolCallInferenceSchema, ToolCaller
from parlant.core.emissions import EmittedEvent, EventEmitter
from parlant.core.tools import ToolId


class ToolEventGenerator:
    def __init__(
        self,
        logger: Logger,
        correlator: ContextualCorrelator,
        service_registry: ServiceRegistry,
        schematic_generator: SchematicGenerator[ToolCallInferenceSchema],
    ) -> None:
        self._logger = logger
        self._correlator = correlator
        self._service_registry = service_registry

        self._tool_caller = ToolCaller(logger, service_registry, schematic_generator)

    async def generate_events(
        self,
        event_emitter: EventEmitter,
        session_id: SessionId,
        agents: Sequence[Agent],
        user_tags_pair: tuple[EndUser, Sequence[EndUserTag]],
        context_variables: Sequence[tuple[ContextVariable, ContextVariableValue]],
        interaction_history: Sequence[Event],
        terms: Sequence[Term],
        ordinary_guideline_propositions: Sequence[GuidelineProposition],
        tool_enabled_guideline_propositions: Mapping[GuidelineProposition, Sequence[ToolId]],
        staged_events: Sequence[EmittedEvent],
    ) -> Optional[EventGenerationResult]:
        assert len(agents) == 1

        if not tool_enabled_guideline_propositions:
            self._logger.debug("Skipping tool calling; no tools associated with guidelines found")
            return None

        generation_info, tool_calls = await self._tool_caller.infer_tool_calls(
            agents,
            user_tags_pair,
            context_variables,
            interaction_history,
            terms,
            ordinary_guideline_propositions,
            tool_enabled_guideline_propositions,
            staged_events,
        )

        if not tool_calls:
            return EventGenerationResult(generation_info, [])

        tool_results = await self._tool_caller.execute_tool_calls(
            ToolContext(agent_id=agents[0].id, session_id=session_id),
            tool_calls,
        )

        if not tool_results:
            return EventGenerationResult(generation_info, [])

        event_data: ToolEventData = {
            "tool_calls": [
                {
                    "tool_id": r.tool_call.tool_id.to_string(),
                    "arguments": r.tool_call.arguments,
                    "result": r.result,
                }
                for r in tool_results
            ]
        }

        event = await event_emitter.emit_tool_event(
            correlation_id=self._correlator.correlation_id,
            data=event_data,
        )

        return EventGenerationResult(generation_info, [event])
