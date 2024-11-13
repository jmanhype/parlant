import asyncio
from dataclasses import dataclass, asdict
from itertools import chain
import json
import traceback
from typing import Any, Mapping, NewType, Optional, Sequence

from parlant.core.tools import Tool, ToolContext
from parlant.core.agents import Agent
from parlant.core.common import JSONSerializable, generate_id, DefaultBaseModel
from parlant.core.context_variables import ContextVariable, ContextVariableValue
from parlant.core.nlp.generation import GenerationInfo, SchematicGenerator
from parlant.core.services.tools.service_registry import ServiceRegistry
from parlant.core.sessions import Event, ToolResult
from parlant.core.glossary import Term
from parlant.core.engines.alpha.guideline_proposition import GuidelineProposition
from parlant.core.engines.alpha.prompt_builder import PromptBuilder
from parlant.core.engines.alpha.utils import emitted_tool_events_to_dicts
from parlant.core.emissions import EmittedEvent
from parlant.core.logging import Logger
from parlant.core.tools import ToolId, ToolService

ToolCallId = NewType("ToolCallId", str)
ToolResultId = NewType("ToolResultId", str)


class ToolCallEvaluation(DefaultBaseModel):
    name: str
    rationale: str
    applicability_score: int
    arguments: Optional[Mapping[str, Any]] = dict()
    same_call_is_already_staged: bool
    should_run: bool


class ToolCallInferenceSchema(DefaultBaseModel):
    last_user_message: Optional[str] = None
    most_recent_user_inquiry_or_need: Optional[str] = None
    most_recent_user_inquiry_or_need_was_already_resolved: Optional[bool] = False
    tool_call_evaluations: list[ToolCallEvaluation]


@dataclass(frozen=True)
class ToolCall:
    id: ToolCallId
    tool_id: ToolId
    arguments: Mapping[str, JSONSerializable]


@dataclass(frozen=True)
class ToolCallResult:
    id: ToolResultId
    tool_call: ToolCall
    result: ToolResult


class ToolCaller:
    def __init__(
        self,
        logger: Logger,
        service_registry: ServiceRegistry,
        schematic_generator: SchematicGenerator[ToolCallInferenceSchema],
    ) -> None:
        self._service_registry = service_registry
        self._logger = logger
        self._schematic_generator = schematic_generator

    async def infer_tool_calls(
        self,
        agents: Sequence[Agent],
        context_variables: Sequence[tuple[ContextVariable, ContextVariableValue]],
        interaction_history: Sequence[Event],
        terms: Sequence[Term],
        ordinary_guideline_propositions: Sequence[GuidelineProposition],
        tool_enabled_guideline_propositions: Mapping[GuidelineProposition, Sequence[ToolId]],
        staged_events: Sequence[EmittedEvent],
    ) -> tuple[GenerationInfo, Sequence[ToolCall]]:
        async def _get_id_tool_pairs(tool_ids: Sequence[ToolId]) -> Sequence[tuple[ToolId, Tool]]:
            services: dict[str, ToolService] = {}
            tools = []
            for id in tool_ids:
                if id.service_name not in services:
                    services[id.service_name] = await self._service_registry.read_tool_service(
                        id.service_name
                    )
                tools.append((id, await services[id.service_name].read_tool(id.tool_name)))
            return tools

        inference_prompt = self._format_tool_call_inference_prompt(
            agents,
            context_variables,
            interaction_history,
            terms,
            ordinary_guideline_propositions,
            {
                p: await _get_id_tool_pairs(tool_ids)
                for p, tool_ids in tool_enabled_guideline_propositions.items()
            },
            staged_events,
        )

        with self._logger.operation("Tool classification"):
            generation_info, inference_output = await self._run_inference(inference_prompt)

        tool_calls_that_need_to_run = [
            c for c in inference_output if not c.same_call_is_already_staged
        ]

        return generation_info, [
            ToolCall(
                id=ToolCallId(generate_id()),
                tool_id=ToolId.from_string(tc.name),
                arguments=tc.arguments,
            )
            for tc in tool_calls_that_need_to_run
            if tc.should_run and tc.applicability_score >= 7
        ]

    async def execute_tool_calls(
        self,
        context: ToolContext,
        tool_calls: Sequence[ToolCall],
    ) -> Sequence[ToolCallResult]:
        with self._logger.operation("Tool calls"):
            tool_results = await asyncio.gather(
                *(
                    self._run_tool(
                        context=context,
                        tool_call=tool_call,
                        tool_id=tool_call.tool_id,
                    )
                    for tool_call in tool_calls
                )
            )

            return tool_results

    def _format_tool_call_inference_prompt(
        self,
        agents: Sequence[Agent],
        context_variables: Sequence[tuple[ContextVariable, ContextVariableValue]],
        interaction_event_list: Sequence[Event],
        terms: Sequence[Term],
        ordinary_guideline_propositions: Sequence[GuidelineProposition],
        tool_enabled_guideline_propositions: Mapping[
            GuidelineProposition, Sequence[tuple[ToolId, Tool]]
        ],
        staged_events: Sequence[EmittedEvent],
    ) -> str:
        assert len(agents) == 1

        id_tool_pairs = list(chain(*tool_enabled_guideline_propositions.values()))

        proposition_tool_ids = {
            p: [t_id for t_id, _ in pairs]
            for p, pairs in tool_enabled_guideline_propositions.items()
        }

        staged_calls = self._get_staged_calls(staged_events)

        builder = PromptBuilder()

        ### NEW PROMPT
        builder.add_section(
            """
###
GENERAL INSTRUCTIONS
###
You are part of a system of AI agents which interact with a user on the behalf of a business.
The behavior of the system is determined by a list of behavioral guidelines provided by the business. 
Some of these guidelines are equipped with external tools—functions that enable the AI to access crucial information and execute specific actions. 
Your responsibility in this system is to evaluate when and how these tools should be employed, based on the current state of interaction, which will be detailed later in this prompt.

This evaluation and execution process occurs iteratively, preceding each response generated for the user. 
Consequently, some tool calls may have already been initiated and executed following the user's most recent message. 
Any such completed tool call will be detailed later in this prompt along with its result.
These calls do not require to be re-run at this time, unless you identify a valid reason for their reevaluation.


"""
        )
        builder.add_agent_identity(agents[0])
        builder.add_section(
            f"""
###
TASK DESCRIPTION
###
Your task is to review the available tools and, based on your most recent interaction with the user, decide whether to use each one. 
For each tool, assign a score from 1 to 10 to indicate its usefulness at this time. 
For any tool with a score of 5 or higher, provide the arguments for activation, following the format in its description.

While doing so, take the following instructions into account:

1. You may suggest tools that don’t directly address the user’s latest interaction but can advance the conversation to a more useful state based on function definitions.
2. Each tool may be called multiple times with different arguments.
3. Avoid calling a tool with the same arguments more than once, unless clearly justified by the interaction.
4. Ensure each tool call relies only on the immediate context and staged calls, without requiring other tools not yet invoked, to avoid dependencies.
5. Use the "should_run" argument to indicate whether a tool should be executed, meaning it has a high applicability score and either (a) has not been staged with the same arguments, or (b) was staged but needs to be re-executed.

Produce a valid JSON object according to the following format:

{{
    "tool_call_evaluations": [
        {{
            "name": "<TOOL NAME>",
            "rationale": "<A FEW WORDS THAT EXPLAIN WHETHER AND HOW THE TOOL NEEDS TO BE CALLED>",
            "applicability_score": <INTEGER FROM 1 TO 10>,
            "arguments": <ARGUMENTS FOR THE TOOL>,
            "same_call_is_already_staged": <BOOLEAN>,
            "should_run": <BOOL>,
        }},
        ...,
        {{
            "name": "<TOOL NAME>",
            "rationale": "<A FEW WORDS THAT EXPLAIN WHETHER AND HOW THE TOOL NEEDS TO BE CALLED>",
            "applicability_score": <INTEGER FROM 1 TO 10>,
            "arguments": <ARGUMENTS FOR THE TOOL>,
            "same_call_is_already_staged": <BOOLEAN>,
            "should_run": <BOOL>,
        }}
    ]
}}

where each tool provided to you under appears at least once in "tool_call_evaluations", whether you decide to use it or not.

The following examples show correct outputs for various hypothetical situations. 
Only the responses are provided, without the interaction history or tool descriptions, though these can be inferred from the responses:
###
Example 1:

Context - check_balance(12345) is the only staged tool call
###
{{
    "last_user_message": "Do I have enough money in my account to get a taxi from New York to Newark?",
    "most_recent_user_inquiry_or_need": "Checking the user's balance, comparing it to the price of a taxi from New York to Newark, and report the result to the user",
    "most_recent_user_inquiry_or_need_was_already_resolved": false,
    "tool_call_evaluations": [
        {{
            "name": "check_balance",
            "rationale": "We need the client's current balance to respond to their question",
            "applicability_score": 9,
            "arguments": {{
                "user_id": "12345",
            }}
            "same_call_is_already_staged": true,
            "should_run": false
        }},
        {{
            "name": "ping_supervisor",
            "rationale": "There's no reason to notify the supervisor of anything",
            "applicability_score": 1,
            "same_call_is_already_staged": false,
            "should_run": false
        }},
        {{
            "name": "check_ride_price",
            "rationale": "We need to know the price of a ride from New York to Newark to respond to the user",
            "applicability_score": 9,
            "arguments": {{
                "origin": "New York",
                "Destination": "Newark",
            }}
            "same_call_is_already_staged": false,
            "should_run": true
        }},
        {{
            "name": "order_taxi",
            "rationale": "The client hasn't asked for a taxi to be ordered yet",
            "applicability_score": 2,
            "same_call_is_already_staged": false
        }},
    ]
}}
###

"""  # noqa TODO add another example? Or change title to clarify it's a single example
        )
        builder.add_context_variables(context_variables)
        builder.add_glossary(terms)
        builder.add_interaction_history(interaction_event_list)
        builder.add_guideline_propositions(
            ordinary_guideline_propositions,
            proposition_tool_ids,
            include_priority=False,
            include_tool_associations=True,
        )
        builder.add_tool_definitions(id_tool_pairs)
        if staged_calls:
            builder.add_section(
                f"""
The following is a list of tool calls staged after the interaction’s latest state. Use this information to avoid redundant calls and to guide your response.

Reminder: If a tool is already staged with the exact same arguments, set "same_call_is_already_staged" to true. 
You may still choose to re-run the tool call, but only if there is a specific reason for it to be executed multiple times.

The staged tool calls are:
{staged_calls}
###
"""
            )
        else:
            builder.add_section(
                """
STAGED TOOL CALLS
-----------------
There are no staged tool calls at this time.
###
"""
            )

        prompt = builder.build()  # TODO delete
        with open("tool_call_inference_prompt.txt", "w") as f:
            f.write(prompt)
        return builder.build()

    def _get_staged_calls(
        self,
        emitted_events: Sequence[EmittedEvent],
    ) -> Optional[str]:
        staged_calls = list(
            chain(*[e["data"] for e in emitted_tool_events_to_dicts(emitted_events)])
        )

        if not staged_calls:
            return None

        return json.dumps(
            [
                {
                    "tool_id": invocation["tool_id"],
                    "arguments": invocation["arguments"],
                    "result": invocation["result"],
                }
                for invocation in staged_calls
            ]
        )

    async def _run_inference(
        self,
        prompt: str,
    ) -> tuple[GenerationInfo, Sequence[ToolCallEvaluation]]:
        self._logger.debug(f"Tool call inference prompt: {prompt}")

        inference = await self._schematic_generator.generate(
            prompt=prompt,
            hints={"temperature": 0.3},
        )

        self._logger.debug(
            f"Tool call request results: {json.dumps([t.model_dump(mode="json") for t in inference.content.tool_call_evaluations], indent=2),}"
        )
        return inference.info, inference.content.tool_call_evaluations

    async def _run_tool(
        self,
        context: ToolContext,
        tool_call: ToolCall,
        tool_id: ToolId,
    ) -> ToolCallResult:
        try:
            self._logger.debug(
                f"Tool call executing: {tool_call.tool_id.to_string()}/{tool_call.id}"
            )
            service = await self._service_registry.read_tool_service(tool_id.service_name)
            result = await service.call_tool(
                tool_id.tool_name,
                context,
                tool_call.arguments,
            )
            self._logger.debug(
                f"Tool call returned: {tool_call.tool_id.to_string()}/{tool_call.id}: {json.dumps(asdict(result), indent=2)}"
            )

            return ToolCallResult(
                id=ToolResultId(generate_id()),
                tool_call=tool_call,
                result={
                    "data": result.data,
                    "metadata": result.metadata,
                    "control": result.control,
                },
            )
        except Exception as e:
            self._logger.error(
                f"Tool execution error (tool='{tool_call.tool_id.to_string()}', "
                "arguments={tool_call.arguments}): " + "\n".join(traceback.format_exception(e)),
            )

            return ToolCallResult(
                id=ToolResultId(generate_id()),
                tool_call=tool_call,
                result={
                    "data": "Tool call error",
                    "metadata": {"error_details": str(e)},
                    "control": {},
                },
            )
