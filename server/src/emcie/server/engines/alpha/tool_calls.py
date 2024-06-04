import asyncio
import importlib
import itertools
import json
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
        applied_score: int
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
            tools_requests_calls = await self._list_tools_requests(tools_requests_prompt)

        tools_requests_checks_prompt = self._format_tools_requests_checks_prompt(
            interaction_history,
            guidelines,
            guideline_tools_associations,
            produced_tool_events,
            tools_requests_calls,
        )

        with duration_logger("Tool calls"):
            tools_calls = await self._list_tools_calls(tools_requests_checks_prompt)

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

In generating the response, you must adhere to the following rules: ###
{rules}
###

The following is a list of instructions that apply, along with the functions related to them, which may or may not apply: ###
{functions_rules}
###

The following are the function definitions: ###
{functions}
###

The following is a list of ordered invoked functions after the interaction's latest state.
Use this information to avoid redundant calls and inform your response: ###
{invoked_functions}
###

Generate your response by taking into consideration the following steps, and score the response based on adherence to these steps:

1. Determine the functions that need to be called based on the provided instructions and the interaction's latest state.
2. It is permissible to propose functions that do not directly answer the interaction's latest state but can compute based on the function definitions to promote a more advanced state for answering.
3. A function may be called multiple times with different parameters.
4. If a function is not called at all, it must still be mentioned in the results.
5. Avoid calling a function that has already been called with the same parameters.
6. Ensure that each function proposed for invocation relies solely on the immediate context and previously invoked functions, without depending on other functions yet to be invoked. This prevents the proposal of interconnected functions unless their dependencies are already satisfied by previous calls.

Produce a valid JSON object in the format shown in the following example:

{{
    "tools_requests_calls": [
        {{
            "name": "<FUNCTION NAME>",
            "rationale": "<A FEW WORDS THAT EXPLAIN WHY THE FUNCTION NEEDS TO BE CALLED OR NOT CALLED>",
            "applied_score": <INTEGER FROM 1 TO 10>,
            "parameters": <PARAMETERS FOR THE FUNCTION IF CALLED, OTHERWISE AN EMPTY OBJECT>
        }},
        ...,
        {{
            "name": "<FUNCTION NAME>",
            "rationale": "<A FEW WORDS THAT EXPLAIN WHY THE FUNCTION NEEDS TO BE CALLED OR NOT CALLED>",
            "applied_score": <INTEGER FROM 1 TO 10>,
            "parameters": <PARAMETERS FOR THE FUNCTION IF CALLED, OTHERWISE AN EMPTY OBJECT>
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

In generating the response, you must adhere to the following rules and their related tools: ###
{rules}
###

The following is a list of instructions that apply, along with the functions related to them, which may or may not apply: ###
{functions_rules}
###

The following are the function definitions: ###
{functions}
###

The following is a list of ordered invoked functions after the interaction's latest state.
Use this information to avoid redundant calls and inform your response: ###
{invoked_functions}
###

The following is the proposed list of functions that need to be called. It is permissible to propose functions that do not directly answer the interaction's latest state but can compute based on the function definitions to promote a more advanced state for answering: ###
{tools_requests_calls}
###

Generate your response by taking into consideration the following steps, and score the response based on adherence to these steps:

1. Verify if the proposed functions adhere to the provided instructions and the interaction's latest state.
2. Verify that the parameters provided for each function call are correct and in accordance with their defined parameters in the function definitions. 
3. Ensure that each function proposed for invocation does not depend on other functions yet to be invoked. Use only the immediate context and previously invoked functions for reference. This maintains accurate and relevant tool proposals.
4. Avoid calling a function that has already been called with the same parameters. If a function with the same parameters has already been invoked, its applied score should be 0.
5. A function may be called multiple times with different parameters.
6. If a function is not called at all, it must still be mentioned in the results.

Produce a valid JSON object in the format shown in the following example:

{{
    "checks": [
        {{
            "name": "<FUNCTION NAME>",
            "rationale": "<A FEW WORDS THAT EXPLAIN WHY THE FUNCTION NEEDS TO BE CALLED OR NOT CALLED>",
            "parameters": <PARAMETERS FOR THE FUNCTION IF CALLED, OTHERWISE AN EMPTY OBJECT>,
            "parameters_rationale": <"A FEW WORDS EXPLAINING THE PARAMETERS' POPULATION AND THEIR TYPE CORRECTNESS">,
            "parameters_correct": <BOOLEAN>,
            "applied_score": <INTEGER FROM 1 TO 10>
        }},
        ...,
        {{
            "name": "<FUNCTION NAME>",
            "rationale": "<A FEW WORDS THAT EXPLAIN WHY THE FUNCTION NEEDS TO BE CALLED OR NOT CALLED>",
            "parameters": <PARAMETERS FOR THE FUNCTION IF CALLED, OTHERWISE AN EMPTY OBJECT>,
            "parameters_rationale": <"A FEW WORDS EXPLAINING THE PARAMETERS' POPULATION AND THEIR TYPE CORRECTNESS">,
            "parameters_correct": <BOOLEAN>,
            "applied_score": <INTEGER FROM 1 TO 10>
        }}
    ]
}}
Note that the `checks` list can be empty if no functions need to be called.
"""  # noqa

    async def _list_tools_requests(
        self,
        prompt: str,
    ) -> Iterable[ToolCallRequest]:
        response = await self._llm_client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="gpt-4o",
            response_format={"type": "json_object"},
            temperature=0.5,
        )

        content = response.choices[0].message.content or ""

        json_content: Iterable[ToolCaller.ToolCallRequest] = json.loads(content)[
            "tools_requests_calls"
        ]

        return json_content

    async def _list_tools_calls(
        self,
        prompt: str,
    ) -> Iterable[ToolCall]:
        response = await self._llm_client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="gpt-4o",
            response_format={"type": "json_object"},
            temperature=0.8,
        )

        content = response.choices[0].message.content or ""

        json_content = json.loads(content)["checks"]

        tools_calls = [
            ToolCall(
                id=ToolCallId(generate_id()),
                name=t["name"],
                parameters=t["parameters"],
            )
            for t in json_content
            if t["applied_score"] >= 8 and t["parameters_correct"]
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
