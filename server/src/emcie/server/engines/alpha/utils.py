from contextlib import contextmanager
import json
import os
import time
from typing import Any, Iterable, Literal
from loguru import logger
from openai import AsyncClient

from emcie.server.core.guidelines import Guideline
from emcie.server.core.sessions import Event
from emcie.server.core.tools import Tool
from emcie.server.engines.common import ProducedEvent, ToolResult


def make_llm_client(provider: Literal["openai", "together"]) -> AsyncClient:
    if provider == "openai":
        return AsyncClient(api_key=os.environ["OPENAI_API_KEY"])
    elif provider == "together":
        return AsyncClient(
            api_key=os.environ["TOGETHER_API_KEY"],
            base_url="https://api.together.xyz/v1",
        )


@contextmanager
def duration_logger(operation_name: str) -> Any:
    t_start = time.time()

    try:
        yield
    finally:
        t_end = time.time()
        logger.info(f"{operation_name} took {round(t_end - t_start, 3)}s")


def events_to_json(events: Iterable[Event]) -> str:
    event_dicts = [event_to_dict(e) for e in events]
    return json.dumps(event_dicts)


def event_to_dict(event: Event) -> dict[str, Any]:
    return {
        "id": event.id,
        "type": event.type,
        "source": {
            "client": "user",
            "server": "assistant",
        }.get(event.source),
        "data": event.data,
    }


def produced_tools_events_to_json(produced_events: Iterable[ProducedEvent]) -> str:
    produced_event_dicts = [produced_tools_event_to_dict(e) for e in produced_events]
    return json.dumps(produced_event_dicts)


def produced_tools_event_to_dict(produced_event: ProducedEvent) -> dict[str, Any]:
    return {
        "type": produced_event.type,
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


def tools_guidelines_to_string(
    tools_guidelines: dict[Guideline, Iterable[Tool]],
) -> str:
    def _list_tools_names(
        tools: Iterable[Tool],
    ) -> str:
        return str([t.name for t in tools])

    return "\n\n".join(
        f"{i}) When {g.predicate}, then {g.content}\n"
        f"Functions related: {_list_tools_names(tools_guidelines[g])}"
        for i, g in enumerate(tools_guidelines, start=1)
    )


def tools_to_json(
    tools: Iterable[Tool],
) -> list[dict[str, Any]]:
    return [tool_to_dict(t) for t in tools]


def tool_to_dict(
    tool: Tool,
) -> dict[str, Any]:
    return {
        "name": tool.name,
        "description": tool.description,
        "parameters": tool.parameters,
        "required": tool.required,
    }


def format_rules_prompt(
    guidelines: Iterable[Guideline],
) -> str:
    rules = "\n".join(
        f"{i}) When {g.predicate}, then {g.content}" for i, g in enumerate(guidelines, start=1)
    )
    return (
        f"""\
In generating the response, you must adhere to the following rules and their related tools: ###
{rules}
###
"""
        if rules
        else ""
    )


def format_rules_associated_to_functions_prompt(
    tools_guidelines: dict[Guideline, Iterable[Tool]],
) -> str:
    if tools_guidelines:
        return f"""\
            
            {tools_guidelines_to_string(tools_guidelines)}
            ###
            """
    return ""
