from contextlib import contextmanager
import json
import os
import time
from typing import Any, Iterable, Literal
from loguru import logger
from openai import AsyncClient

from emcie.server.core.guidelines import Guideline, GuidelineId
from emcie.server.core.sessions import Event
from emcie.server.core.tools import Tool
from emcie.server.engines.alpha.guideline_tool_associations import GuidelineToolAssociation
from emcie.server.engines.common import ProducedEvent
from emcie.server.engines.alpha.tool_calls import ToolResult


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


def produced_tools_events_to_json(
    produced_events: Iterable[ProducedEvent],
) -> list[dict[str, Any]]:
    return [produced_tools_event_to_dict(e) for e in produced_events]


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


async def divide_guidelines_by_tool_association(
    guidelines: Iterable[Guideline],
    associations: dict[GuidelineId, set[GuidelineToolAssociation]],
) -> tuple[Iterable[Guideline], Iterable[Guideline]]:
    guidelines_without_tools = []
    guidelines_with_tools = []
    for guideline in guidelines:
        if guideline.id in associations:
            guidelines_with_tools.append(guideline)
        else:
            guidelines_without_tools.append(guideline)
    return guidelines_without_tools, guidelines_with_tools


async def list_associated_tools(
    tools: Iterable[Tool],
    guideline_id: GuidelineId,
    associations: dict[GuidelineId, set[GuidelineToolAssociation]],
) -> Iterable[Tool]:
    """
    Get the tools associated with a guideline.
    """
    tool_ids_associate_to_guideline = [a.tool_id for a in associations[guideline_id]]

    return [tool for tool in tools if tool.id in tool_ids_associate_to_guideline]


async def map_guidelines_to_associated_tools(
    tools: Iterable[Tool],
    guidelines: Iterable[Guideline],
    associations: dict[GuidelineId, set[GuidelineToolAssociation]],
) -> dict[Guideline, Iterable[Tool]]:
    return {
        guideline: await list_associated_tools(tools, guideline.id, associations)
        for guideline in guidelines
    }
