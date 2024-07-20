import asyncio
from dataclasses import dataclass
import importlib
import inspect
from itertools import chain
import json
import jsonfinder  # type: ignore
from typing import Any, Iterable, Mapping, NewType, Optional, Sequence, TypedDict

from loguru import logger

from emcie.server.core.agents import Agent
from emcie.server.core.common import JSONSerializable, generate_id
from emcie.server.core.context_variables import ContextVariable, ContextVariableValue
from emcie.server.core.guidelines import Guideline
from emcie.server.core.sessions import Event
from emcie.server.core.tools import Tool

from emcie.server.engines.alpha.guideline_proposition import GuidelineProposition
from emcie.server.engines.alpha.prompt_builder import PromptBuilder
from emcie.server.engines.alpha.utils import (
    duration_logger,
    make_llm_client,
    produced_tool_events_to_dict,
)
from emcie.server.engines.common import (
    ProducedEvent,
)

ToolCallId = NewType("ToolCallId", str)
ToolResultId = NewType("ToolResultId", str)


@dataclass(frozen=True)
class ToolCall:
    id: ToolCallId
    name: str
    parameters: dict[str, Any]


@dataclass(frozen=True)
class ToolResult:
    id: ToolResultId
    tool_call: ToolCall
    result: JSONSerializable


class ToolCaller:
    class ToolCallRequest(TypedDict):
        name: str
        parameters: dict[str, Any]
        applicability_score: int
        rationale: str

    def __init__(
        self,
    ) -> None:
        self._llm_client = make_llm_client("openai")

    async def infer_tool_calls(
        self,
        agents: Sequence[Agent],
        context_variables: Sequence[tuple[ContextVariable, ContextVariableValue]],
        interaction_history: Sequence[Event],
        ordinary_guideline_propositions: Sequence[GuidelineProposition],
        tool_enabled_guideline_propositions: Mapping[GuidelineProposition, Sequence[Tool]],
        produced_tool_events: Sequence[ProducedEvent],
    ) -> Sequence[ToolCall]:
        inference_prompt = self._format_tool_call_inference_prompt(
            agents,
            context_variables,
            interaction_history,
            ordinary_guideline_propositions,
            tool_enabled_guideline_propositions,
            produced_tool_events,
        )

        with duration_logger("Tool classification"):
            inference_output = await self._run_inference(inference_prompt)

        verification_prompt = self._format_tool_call_verification_prompt(
            agents,
            context_variables,
            interaction_history,
            ordinary_guideline_propositions,
            tool_enabled_guideline_propositions,
            produced_tool_events,
            inference_output,
        )

        with duration_logger("Tool verification"):
            return await self._verify_inference(verification_prompt)

    async def execute_tool_calls(
        self,
        tool_calls: Iterable[ToolCall],
        tools: Iterable[Tool],
    ) -> list[ToolResult]:
        tools_by_name = {t.name: t for t in tools}

        with duration_logger("Tool calls"):
            tool_results = await asyncio.gather(
                *(
                    self._run_tool(
                        tool_call=tool_call,
                        tool=tools_by_name[tool_call.name],
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
        ordinary_guideline_propositions: Sequence[GuidelineProposition],
        tool_enabled_guideline_propositions: Mapping[GuidelineProposition, Sequence[Tool]],
        produced_tool_events: Sequence[ProducedEvent],
    ) -> str:
        assert len(agents) == 1

        staged_function_calls = self._get_invoked_functions(produced_tool_events)
        tools = list(chain(*tool_enabled_guideline_propositions.values()))

        builder = PromptBuilder()

        builder.add_agent_identity(agents[0])
        builder.add_interaction_history(interaction_event_list)
        builder.add_context_variables(context_variables)

        builder.add_section(
            """
Before generating your next response, you are highly encouraged to use tools that are provided to you, in order to generate a high-quality, well-informed response.
"""  # noqa
        )

        builder.add_guideline_propositions(
            ordinary_guideline_propositions,
            tool_enabled_guideline_propositions,
            include_priority=False,
            include_tool_associations=True,
        )

        builder.add_tool_definitions(tools)

        if staged_function_calls:
            builder.add_section(
                f"""
The following is a list of ordered invoked tool functions after the interaction's latest state.
You can use this information to avoid redundant calls and inform your response.
For example, if the data you need already exists in one of these calls, then you DO NOT
need to ask for this tool function to be run again, because its information is fresh here!: ###
{staged_function_calls}
###
"""
            )

        builder.add_section(
            f"""
Before generating your next response, you must now decide whether to use any of the tools provided.
Here are the principles by which you can decide whether to use tools:

1. Determine the tool functions that need to be called based on the provided instructions and the interaction's latest state.
2. It is permissible to propose tool functions that do not directly answer the interaction's latest state but can compute based on the function definitions to promote a more advanced state for answering.
3. A tool function may be called multiple times with different parameters.
4. If a tool function is not called at all, it must still be mentioned in the results!
5. Avoid calling a tool function that has already been called with the same parameters!
6. Ensure that each function proposed for invocation relies solely on the immediate context and previously invoked functions, without depending on other functions yet to be invoked. This prevents the proposal of interconnected functions unless their dependencies are already satisfied by previous calls.

Produce a valid JSON object according to the following format:

{{
    "tool_call_specifications": [
        {{
            "name": "<FUNCTION NAME>",
            "rationale": "<A FEW WORDS THAT EXPLAIN WHETHER AND WHY THE TOOL FUNCTION NEEDS TO BE CALLED>",
            "applicability_score": <INTEGER FROM 1 TO 10>,
            "should_run": <BOOLEAN>,
            "parameters": <PARAMETERS FOR THE TOOL FUNCTION>
        }},
        ...,
        {{
            "name": "<FUNCTION NAME>",
            "rationale": "<A FEW WORDS THAT EXPLAIN WHETHER AND WHY THE TOOL FUNCTION NEEDS TO BE CALLED>",
            "applicability_score": <INTEGER FROM 1 TO 10>,
            "should_run": <BOOLEAN>,
            "parameters": <PARAMETERS FOR THE TOOL FUNCTION>
        }}
    ]
}}

Here's a hypothetical example, for your reference:

{{
    "tool_call_specifications": [
        {{
            "name": "transfer_money",
            "rationale": "Jack owes John $5",
            "applicability_score": 9,
            "should_run": true,
            "parameters": {{
                "from": "Jack",
                "to": "John",
                "amount": 5.00
            }}
        }},
        ...,
        {{
            "name": "loan_money",
            "rationale": "There's no obvious reason for Jack to loan any money to anyone",
            "applicability_score": 2,
            "should_run": false
        }}
    ]
}}


Note that the `tool_call_specifications` list can be empty if no functions need to be called.
"""  # noqa
        )

        return builder.build()

    def _get_invoked_functions(
        self,
        produced_events: Iterable[ProducedEvent],
    ) -> Optional[str]:
        ordered_function_invocations = list(
            chain(*[e["data"] for e in produced_tool_events_to_dict(produced_events)])
        )

        if not ordered_function_invocations:
            return None

        return json.dumps(
            [
                {
                    "function_name": invocation["tool_name"],
                    "parameters": invocation["parameters"],
                    "result": invocation["result"],
                }
                for invocation in ordered_function_invocations
            ]
        )

    def _format_tool_call_verification_prompt(
        self,
        agents: Sequence[Agent],
        context_variables: Sequence[tuple[ContextVariable, ContextVariableValue]],
        interaction_event_list: Sequence[Event],
        ordinary_guideline_propositions: Sequence[GuidelineProposition],
        tool_enabled_guideline_propositions: Mapping[GuidelineProposition, Sequence[Tool]],
        produced_tool_events: Sequence[ProducedEvent],
        tool_call_specifications: Sequence[ToolCallRequest],
    ) -> str:
        assert len(agents) == 1

        staged_function_calls = self._get_invoked_functions(produced_tool_events)
        tools = list(chain(*tool_enabled_guideline_propositions.values()))

        builder = PromptBuilder()

        builder.add_agent_identity(agents[0])
        builder.add_interaction_history(interaction_event_list)
        builder.add_context_variables(context_variables)

        builder.add_section(
            """
Before generating your next response, you are highly encouraged to use tools that are provided to you, in order to generate a high-quality, well-informed response.
"""  # noqa
        )

        builder.add_guideline_propositions(
            ordinary_guideline_propositions,
            tool_enabled_guideline_propositions,
            include_priority=False,
            include_tool_associations=True,
        )

        builder.add_tool_definitions(tools)

        if staged_function_calls:
            builder.add_section(
                f"""
The following is a list of ordered invoked tool functions after the interaction's latest state.
You can use this information to avoid redundant calls and inform your response: ###
{staged_function_calls}
###
"""
            )

        builder.add_section(
            f"""
A predictive NLP algorithm has suggested that the following tool calls be executed
prior to generating your next response to the user. ###
{tool_call_specifications}
###

Before generating your next response, you must now first decide whether to go ahead and execute
any of the tool calls proposed. Here are the principles by which you can decide whether to do so:

1. Verify if the proposed tool functions adhere to the provided instructions and the interaction's latest state.
2. Verify that the parameters provided for each tool function call are correct and in accordance with their defined parameters in the function definitions.
3. Ensure that each function proposed for invocation does not depend on other functions yet to be invoked. Use only the immediate context and previously invoked functions for reference. This maintains accurate and relevant tool proposals.
4. Avoid repeating a tool function with the same exact set of parameters.
5. However, a function may indeed be called multiple times with different parameters.
6. If a function is not called at all, it must still be mentioned in the results.

Produce a valid JSON object according to the following format:

{{
    "checks": [
        {{
            "name": "<FUNCTION NAME>",
            "rationale": "<A FEW WORDS THAT EXPLAIN WHY THE TOOL FUNCTION NEEDS TO BE CALLED OR NOT CALLED>",
            "applicability_score": <INTEGER FROM 1 TO 10>,
            "should_run": <BOOLEAN>,
            "parameters": <PARAMETERS FOR THE TOOL FUNCTION IF CALLED, OTHERWISE AN EMPTY OBJECT>,
            "parameters_rationale": <"A FEW WORDS EXPLAINING THE CHOICE OF PARAMETERS AND THEIR TYPE CORRECTNESS">,
            "parameters_correct": <BOOLEAN>
        }},
        ...,
        {{
            "name": "<FUNCTION NAME>",
            "rationale": "<A FEW WORDS THAT EXPLAIN WHY THE TOOL FUNCTION NEEDS TO BE CALLED OR NOT CALLED>",
            "applicability_score": <INTEGER FROM 1 TO 10>,
            "should_run": <BOOLEAN>,
            "parameters": <PARAMETERS FOR THE FUNCTION IF CALLED, OTHERWISE AN EMPTY OBJECT>,
            "parameters_rationale": <"A FEW WORDS EXPLAINING THE CHOICE OF PARAMETERS AND THEIR TYPE CORRECTNESS">,
            "parameters_correct": <BOOLEAN>
        }}
    ]
}}

Here's a hypothetical example, for your reference:

{{
    "checks": [
        {{
            "name": "transfer_money",
            "rationale": "Jack owes John $5",
            "applicability_score": 9,
            "should_run": true,
            "parameters": {{
                "from": "Jack",
                "to": "John",
                "amount": 5.00
            }},
            "parameters_rationale": "$5 should be transferred from Jack to John",
            "parameters_correct": true
        }},
        ...,
        {{
            "name": "loan_money",
            "rationale": "There's no obvious reason for Jack to loan any money to anyone",
            "applicability_score": 2,
            "should_run": false
        }}
    ]
}}

Note that the `checks` list can be empty if no functions need to be called.
"""  # noqa
        )

        return builder.build()

    async def _run_inference(
        self,
        prompt: str,
    ) -> Sequence[ToolCallRequest]:
        response = await self._llm_client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="gpt-4o",
            response_format={"type": "json_object"},
            temperature=0.3,
        )

        content = response.choices[0].message.content or ""
        json_content = jsonfinder.only_json(content)[2]

        logger.debug(
            f"Tool call request results: {json.dumps(
                json_content['tool_call_specifications'], indent=2
                )}"
        )
        return json_content["tool_call_specifications"]  # type: ignore

    async def _verify_inference(
        self,
        prompt: str,
    ) -> Sequence[ToolCall]:
        response = await self._llm_client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="gpt-4o",
            response_format={"type": "json_object"},
            temperature=0.3,
        )

        content = response.choices[0].message.content or "{}"
        checks = jsonfinder.only_json(content)[2]["checks"]

        tools_calls = [
            ToolCall(
                id=ToolCallId(generate_id()),
                name=t["name"],
                parameters=t["parameters"],
            )
            for t in checks
            if t["should_run"] and t["applicability_score"] >= 7 and t["parameters_correct"]
        ]

        return tools_calls

    async def _run_tool(
        self,
        tool_call: ToolCall,
        tool: Tool,
    ) -> ToolResult:
        try:
            module = importlib.import_module(tool.module_path)
            func = getattr(module, tool_call.name)
        except Exception as e:
            logger.error(f"ERROR IN LOADING TOOL {tool_call.name}: " + str(e))
            return ToolResult(
                id=ToolResultId(generate_id()),
                tool_call=tool_call,
                result=str(e),
            )

        try:
            logger.debug(f"Tool call executing: {tool_call.name}/{tool_call.id}")

            result = func(**tool_call.parameters)

            if inspect.isawaitable(result):
                result = await result

            result = json.dumps(result)

            logger.debug(f"Tool call returned: {tool_call.name}/{tool_call.id}: {result}")
        except Exception as e:
            logger.warning(f"Tool call produced an error: {tool_call.name}/{tool_call.id}: {e}")
            result = str(e)

        return ToolResult(
            id=ToolResultId(generate_id()),
            tool_call=tool_call,
            result=result,
        )
