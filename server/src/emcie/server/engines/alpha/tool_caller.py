import asyncio
from dataclasses import dataclass
import importlib
import inspect
from itertools import chain
import json
import jsonfinder  # type: ignore
from typing import Any, Iterable, NewType, Optional, TypedDict

from loguru import logger

from emcie.server.core.common import generate_id
from emcie.server.core.context_variables import ContextVariable, ContextVariableValue
from emcie.server.core.guidelines import Guideline
from emcie.server.core.sessions import Event
from emcie.server.core.tools import Tool

from emcie.server.engines.alpha.utils import (
    context_variables_to_json,
    duration_logger,
    events_to_json,
    make_llm_client,
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
    result: Any


def produced_tools_events_to_dict(
    produced_events: Iterable[ProducedEvent],
) -> list[dict[str, Any]]:
    return [produced_tools_event_to_dict(e) for e in produced_events]


def produced_tools_event_to_dict(produced_event: ProducedEvent) -> dict[str, Any]:
    return {
        "kind": produced_event.kind,
        "data": [
            tool_result_to_dict(tool_result) for tool_result in produced_event.data["tools_result"]
        ],
    }


def tool_result_to_dict(
    tool_result: ToolResult,
) -> dict[str, Any]:
    return {
        "tool_name": tool_result.tool_call.name,
        "parameters": tool_result.tool_call.parameters,
        "result": tool_result.result,
    }


def tool_to_dict(
    tool: Tool,
) -> dict[str, Any]:
    return {
        "name": tool.name,
        "description": tool.description,
        "parameters": tool.parameters,
        "required": tool.required,
    }


def tools_to_json(
    tools: Iterable[Tool],
) -> list[dict[str, Any]]:
    return [tool_to_dict(t) for t in tools]


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
        context_variables: list[tuple[ContextVariable, ContextVariableValue]],
        interaction_history: list[Event],
        guidelines: Iterable[Guideline],
        guideline_tools_associations: dict[Guideline, Iterable[Tool]],
        produced_tool_events: Iterable[ProducedEvent],
    ) -> Iterable[ToolCall]:
        inference_prompt = self._format_tool_call_inference_prompt(
            context_variables,
            interaction_history,
            guidelines,
            guideline_tools_associations,
            produced_tool_events,
        )

        with duration_logger("Tools classification"):
            inference_output = await self._run_inference(inference_prompt)

        verification_prompt = self._format_tool_call_verification_prompt(
            context_variables,
            interaction_history,
            guidelines,
            guideline_tools_associations,
            produced_tool_events,
            inference_output,
        )

        with duration_logger("Tool calls"):
            return await self._verify_inference(verification_prompt)

    async def execute_tool_calls(
        self,
        tool_calls: Iterable[ToolCall],
        tools: Iterable[Tool],
    ) -> list[ToolResult]:
        tools_by_name = {t.name: t for t in tools}

        tool_results = await asyncio.gather(
            *[
                self._run_tool(
                    tool_call=tool_call,
                    tool=tools_by_name[tool_call.name],
                )
                for tool_call in tool_calls
            ]
        )

        return tool_results

    def _format_guideline_tool_associations(
        self,
        guideline_tools_associations: dict[Guideline, Iterable[Tool]],
    ) -> str:
        def _list_tools_names(
            tools: Iterable[Tool],
        ) -> str:
            return str([t.name for t in tools])

        return "\n\n".join(
            f"{i}) When {g.predicate}, then {g.content}\n"
            f"Tool functions enabled : {_list_tools_names(guideline_tools_associations[g])}"
            for i, g in enumerate(guideline_tools_associations, start=1)
        )

    def _format_tool_call_inference_prompt(
        self,
        context_variables: list[tuple[ContextVariable, ContextVariableValue]],
        interaction_event_list: list[Event],
        ordinary_guidelines: Iterable[Guideline],
        tool_enabled_guidelines: dict[Guideline, Iterable[Tool]],
        produced_tool_events: Iterable[ProducedEvent],
    ) -> str:
        json_events = events_to_json(interaction_event_list)
        context_values = context_variables_to_json(context_variables)
        staged_function_calls = self._get_invoked_functions(produced_tool_events)
        tools = set(chain(*tool_enabled_guidelines.values()))
        functions = tools_to_json(tools)

        ordinary_rules = "\n".join(
            f"{i}) When {g.predicate}, then {g.content}"
            for i, g in enumerate(ordinary_guidelines, start=1)
        )
        function_enabled_rules = self._format_guideline_tool_associations(tool_enabled_guidelines)

        prompt = ""

        if interaction_event_list:
            prompt += f"""\
The following is a list of events describing a back-and-forth interaction between you,
an AI assistant, and a user: ###
{json_events}
###
"""
        else:
            prompt += """
You, an AI assistant, are now present in an online session with a user.
An interaction may or may not now be initiated by you, addressing the user.

Here's how to decide whether to initiate the interaction:
A. If the rules below both apply to the context, as well as suggest that you should say something
to the user, then you should indeed initiate the interaction now.
B. Otherwise, if no reason is provided that suggests you should say something to the user,
then you should not initiate the interaction. Produce no response in this case.
"""

        if context_variables:
            prompt += f"""
The following is information that you're given about the user and context of the interaction: ###
{context_values}
###
"""

        prompt += """
Before generating your next response, you are highly encouraged to use tools that are provided
to you, in order to generate a high-quality, well-informed response.
"""

        if ordinary_rules:
            prompt += f"""
In generating the response, you must adhere to the following rules: ###
{ordinary_rules}
###
"""

        if function_enabled_rules:
            prompt += f"""
The following is a list of instructions that apply, along with the tool functions enabled for them,
which may or may not need to be called at this point, depending on your judgement
and the rules provided: ###
{function_enabled_rules}
###

The following are the tool function definitions: ###
{functions}
###
"""

        if staged_function_calls:
            prompt += f"""
The following is a list of ordered invoked tool functions after the interaction's latest state.
You can use this information to avoid redundant calls and inform your response.
For example, if the data you need already exists in one of these calls, then you DO NOT
need to ask for this tool function to be run again, because its information is fresh here!: ###
{staged_function_calls}
###
"""

        prompt += f"""
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

        return prompt

    def _get_invoked_functions(
        self,
        produced_events: Iterable[ProducedEvent],
    ) -> Optional[str]:
        ordered_function_invocations = list(
            chain(*[e["data"] for e in produced_tools_events_to_dict(produced_events)])
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
        context_variables: list[tuple[ContextVariable, ContextVariableValue]],
        interaction_event_list: list[Event],
        guidelines: Iterable[Guideline],
        guideline_tool_associations: dict[Guideline, Iterable[Tool]],
        produced_tool_events: Iterable[ProducedEvent],
        tool_call_specifications: Iterable[ToolCallRequest],
    ) -> str:
        json_events = events_to_json(interaction_event_list)
        context_values = context_variables_to_json(context_variables)
        staged_function_calls = self._get_invoked_functions(produced_tool_events)

        tools = set(chain(*guideline_tool_associations.values()))
        functions = tools_to_json(tools)

        ordinary_rules = "\n".join(
            f"{i}) When {g.predicate}, then {g.content}" for i, g in enumerate(guidelines, start=1)
        )
        function_enabled_rules = self._format_guideline_tool_associations(
            guideline_tool_associations
        )

        prompt = ""

        if interaction_event_list:
            prompt += f"""\
The following is a list of events describing a back-and-forth interaction between you,
an AI assistant, and a user: ###
{json_events}
###
"""
        else:
            prompt += """
You, an AI assistant, are now present in an online session with a user.
An interaction may or may not now be initiated by you, addressing the user.

Here's how to decide whether to initiate the interaction:
A. If the rules below both apply to the context, as well as suggest that you should say something
to the user, then you should indeed initiate the interaction now.
B. Otherwise, if no reason is provided that suggests you should say something to the user,
then you should not initiate the interaction. Produce no response in this case.
"""

        if context_variables:
            prompt += f"""
The following is information that you're given about the user and context of the interaction: ###
{context_values}
###
"""

        prompt += """
Before generating your next response, you are highly encouraged to use tools that are provided
to you, in order to generate a high-quality, well-informed response.
"""

        if ordinary_rules:
            prompt += f"""
In generating the response, you must adhere to the following rules: ###
{ordinary_rules}
###
"""

        if function_enabled_rules:
            prompt += f"""
The following is a list of instructions that apply, along with the tool functions enabled for them,
which may or may not need to be called at this point, depending on your judgement
and the rules provided: ###
{function_enabled_rules}
###

The following are the tool function definitions: ###
{functions}
###
"""

        if staged_function_calls:
            prompt += f"""
The following is a list of ordered invoked tool functions after the interaction's latest state.
You can use this information to avoid redundant calls and inform your response: ###
{staged_function_calls}
###
"""

        prompt += f"""
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

        return prompt

    async def _run_inference(
        self,
        prompt: str,
    ) -> Iterable[ToolCallRequest]:
        response = await self._llm_client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="gpt-4o",
            response_format={"type": "json_object"},
            temperature=0.3,
        )

        content = response.choices[0].message.content or ""
        json_content = jsonfinder.only_json(content)[2]

        return json_content["tool_call_specifications"]  # type: ignore

    async def _verify_inference(
        self,
        prompt: str,
    ) -> Iterable[ToolCall]:
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
        module = importlib.import_module(tool.module_path)
        func = getattr(module, tool_call.name)

        try:
            logger.debug(f"Tool call executing: {tool_call.name}/{tool_call.id}")
            if inspect.isawaitable(func):
                result = await func(**tool_call.parameters)  # type: ignore
            else:
                result = func(**tool_call.parameters)
            logger.debug(f"Tool call returned: {tool_call.name}/{tool_call.id}: {result}")
        except Exception as e:
            logger.warning(f"Tool call produced an error: {tool_call.name}/{tool_call.id}: {e}")
            result = e

        return ToolResult(
            id=ToolResultId(generate_id()),
            tool_call=tool_call,
            result=result,
        )
