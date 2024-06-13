import asyncio
import importlib
import itertools
import json
import jsonfinder  # type: ignore
from typing import Any, Iterable, TypedDict
from emcie.server.core.common import generate_id
from emcie.server.core.guidelines import Guideline
from emcie.server.core.sessions import Event
from emcie.server.core.tools import Tool

from emcie.server.engines.alpha.utils import (
    duration_logger,
    events_to_json,
    make_llm_client,
    produced_tools_events_to_json,
    tools_to_json,
)
from emcie.server.engines.common import (
    ProducedEvent,
    ToolCall,
    ToolCallId,
    ToolResult,
    ToolResultId,
)


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

    async def list_tools_result(
        self,
        interaction_history: Iterable[Event],
        guidelines: Iterable[Guideline],
        tools: Iterable[Tool],
        guideline_tools_associations: dict[Guideline, Iterable[Tool]],
        produced_tool_events: Iterable[ProducedEvent],
    ) -> list[ToolResult]:  # sourcery skip: default-mutable-arg
        tools_requests_prompt = self._format_tools_requests_prompt(
            interaction_history,
            guidelines,
            guideline_tools_associations,
            produced_tool_events,
        )

        with duration_logger("Tools classification"):
            tools_requests_calls = await self._propose_tool_calls(tools_requests_prompt)

        tools_requests_checks_prompt = self._format_tools_requests_checks_prompt(
            interaction_history,
            guidelines,
            guideline_tools_associations,
            produced_tool_events,
            tools_requests_calls,
        )

        with duration_logger("Tool calls"):
            tools_calls = await self._review_tool_calls(tools_requests_checks_prompt)

        tools_result = await asyncio.gather(
            *[
                self._proccess_tool(
                    t,
                    tools,
                )
                for t in tools_calls
            ]
        )
        return tools_result

    def _format_guideline_tools_associations(
        self,
        guideline_tools_associations: dict[Guideline, Iterable[Tool]],
    ) -> str:
        def _list_tools_names(
            tools: Iterable[Tool],
        ) -> str:
            return str([t.name for t in tools])

        return "\n\n".join(
            f"{i}) When {g.predicate}, then {g.content}\n"
            f"Functions related: {_list_tools_names(guideline_tools_associations[g])}"
            for i, g in enumerate(guideline_tools_associations, start=1)
        )

    def _format_tools_requests_prompt(
        self,
        interaction_history: Iterable[Event],
        guidelines: Iterable[Guideline],
        guideline_tools_associations: dict[Guideline, Iterable[Tool]],
        produced_tool_events: Iterable[ProducedEvent],
    ) -> str:
        json_events = events_to_json(interaction_history)
        invoked_functions = self._get_invoked_functions(produced_tool_events)
        functions_rules = self._format_guideline_tools_associations(guideline_tools_associations)

        tools_set = {
            tool for tools_list in guideline_tools_associations.values() for tool in tools_list
        }
        functions = tools_to_json(tools_set)

        rules = "\n".join(
            f"{i}) When {g.predicate}, then {g.content}" for i, g in enumerate(guidelines, start=1)
        )

        return f"""\
The following is a list of events describing a back-and-forth interaction between you, an AI assistant, and a user: ###
{json_events}
###

Before generating your next response, you are highly encouraged to use tools that are provided
to you, in order to generate a high-quality, well-informed response.

In generating the response, you must adhere to the following rules: ###
{rules}
###

The following is a list of instructions that apply, along with the tool functions related to them, which may or may not need to be called at this point, depending on your judgement and the rules provided: ###
{functions_rules}
###

The following are the tool function definitions: ###
{functions}
###

The following is a list of ordered invoked tool functions after the interaction's latest state.
You can use this information to avoid redundant calls and inform your response: ###
{invoked_functions}
###

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
    "tools_requests_calls": [
        {{
            "name": "<FUNCTION NAME>",
            "rationale": "<A FEW WORDS THAT EXPLAIN WHETHER AND WHY THE FUNCTION NEEDS TO BE CALLED>",
            "applicability_score": <INTEGER FROM 1 TO 10>,
            "should_run": <BOOLEAN>,
            "parameters": <PARAMETERS FOR THE FUNCTION>
        }},
        ...,
        {{
            "name": "<FUNCTION NAME>",
            "rationale": "<A FEW WORDS THAT EXPLAIN WHETHER AND WHY THE FUNCTION NEEDS TO BE CALLED>",
            "applicability_score": <INTEGER FROM 1 TO 10>,
            "should_run": <BOOLEAN>,
            "parameters": <PARAMETERS FOR THE FUNCTION>
        }}
    ]
}}

Here's a hypothetical example, for your reference:

{{
    "tools_requests_calls": [
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


Note that the `tools_requests_calls` list can be empty if no functions need to be called.
"""  # noqa

    def _get_invoked_functions(
        self,
        produced_events: Iterable[ProducedEvent],
    ) -> str:
        functions_list_by_order = itertools.chain(
            *[e["data"] for e in produced_tools_events_to_json(produced_events)]
        )
        invoked_functions_list = [
            {
                "function_name": f["tool_name"],
                "parameters": f["parameters"],
                "result": f["result"],
            }
            for f in functions_list_by_order
        ]
        return json.dumps(invoked_functions_list)

    def _format_tools_requests_checks_prompt(
        self,
        interaction_history: Iterable[Event],
        guidelines: Iterable[Guideline],
        guideline_tools_associations: dict[Guideline, Iterable[Tool]],
        produced_tool_events: Iterable[ProducedEvent],
        tools_requests_calls: Iterable[ToolCallRequest],
    ) -> str:
        json_events = events_to_json(interaction_history)
        functions_rules = self._format_guideline_tools_associations(guideline_tools_associations)
        invoked_functions = self._get_invoked_functions(produced_tool_events)

        tools_set = {
            tool for tools_list in guideline_tools_associations.values() for tool in tools_list
        }
        functions = tools_to_json(tools_set)

        rules = "\n".join(
            f"{i}) When {g.predicate}, then {g.content}" for i, g in enumerate(guidelines, start=1)
        )

        return f"""\
The following is a list of events describing a back-and-forth interaction between you, an AI assistant, and a user: ###
{json_events}
###

Before generating your next response, you are highly encouraged to use tools that are provided
to you, in order to generate a high-quality, well-informed response.

In generating the response, you must adhere to the following rules: ###
{rules}
###

The following is a list of instructions that apply, along with the tool functions related to them, which may or may not need to be called at this point, depending on your judgement and the rules provided: ###
{functions_rules}
###

The following are the tool function definitions: ###
{functions}
###

The following is a list of ordered invoked tool functions after the interaction's latest state.
You can use this information to avoid redundant calls and inform your response: ###
{invoked_functions}
###

A predictive NLP algorithm has suggested that the following tool calls be executed
prior to generating your next response to the user. ###
{tools_requests_calls}
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
            "rationale": "<A FEW WORDS THAT EXPLAIN WHY THE FUNCTION NEEDS TO BE CALLED OR NOT CALLED>",
            "applicability_score": <INTEGER FROM 1 TO 10>,
            "should_run": <BOOLEAN>,
            "parameters": <PARAMETERS FOR THE FUNCTION IF CALLED, OTHERWISE AN EMPTY OBJECT>,
            "parameters_rationale": <"A FEW WORDS EXPLAINING THE PARAMETERS' POPULATION AND THEIR TYPE CORRECTNESS">,
            "parameters_correct": <BOOLEAN>
        }},
        ...,
        {{
            "name": "<FUNCTION NAME>",
            "rationale": "<A FEW WORDS THAT EXPLAIN WHY THE FUNCTION NEEDS TO BE CALLED OR NOT CALLED>",
            "applicability_score": <INTEGER FROM 1 TO 10>,
            "should_run": <BOOLEAN>,
            "parameters": <PARAMETERS FOR THE FUNCTION IF CALLED, OTHERWISE AN EMPTY OBJECT>,
            "parameters_rationale": <"A FEW WORDS EXPLAINING THE PARAMETERS' POPULATION AND THEIR TYPE CORRECTNESS">,
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

    async def _propose_tool_calls(
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

        return json_content["tools_requests_calls"]  # type: ignore

    async def _review_tool_calls(
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

    async def _proccess_tool(
        self,
        tool_call: ToolCall,
        tools: Iterable[Tool],
    ) -> ToolResult:
        module_path = next((t.module_path for t in tools if t.name == tool_call.name), "")
        module = importlib.import_module(module_path)
        func = getattr(module, tool_call.name)
        result = func(**tool_call.parameters)

        return ToolResult(
            id=ToolResultId(generate_id()),
            tool_call=tool_call,
            result=result,
        )
