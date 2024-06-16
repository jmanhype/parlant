from itertools import chain
import json
from typing import Iterable
from loguru import logger

from emcie.server.core.tools import Tool
from emcie.server.engines.alpha.tool_caller import ToolCaller, produced_tools_events_to_dict
from emcie.server.engines.alpha.utils import (
    events_to_json,
    make_llm_client,
)
from emcie.server.engines.common import ProducedEvent
from emcie.server.core.guidelines import Guideline
from emcie.server.core.sessions import Event


class EventProducer:

    def __init__(self) -> None:
        self.tool_event_producer = ToolsEventProducer()
        self.message_event_producer = MessagesEventProducer()

    async def produce_events(
        self,
        interaction_history: Iterable[Event],
        ordinary_guidelines: Iterable[Guideline],
        tool_enabled_guidelines: dict[Guideline, Iterable[Tool]],
        tools: Iterable[Tool],
    ) -> Iterable[ProducedEvent]:
        tool_events = await self.tool_event_producer.produce_events(
            interaction_history=interaction_history,
            ordinary_guidelines=ordinary_guidelines,
            tool_enabled_guidelines=tool_enabled_guidelines,
            tools=tools,
        )

        message_events = await self.message_event_producer.produce_events(
            interaction_history=interaction_history,
            ordinary_guidelines=ordinary_guidelines,
            tool_enabled_guidelines=tool_enabled_guidelines,
            staged_events=tool_events,
        )

        return chain(tool_events, message_events)


class MessagesEventProducer:
    def __init__(
        self,
    ) -> None:
        self._llm_client = make_llm_client("openai")

    async def produce_events(
        self,
        interaction_history: Iterable[Event],
        ordinary_guidelines: Iterable[Guideline],
        tool_enabled_guidelines: dict[Guideline, Iterable[Tool]],
        staged_events: Iterable[ProducedEvent],
    ) -> Iterable[ProducedEvent]:
        prompt = self._format_prompt(
            interaction_history=interaction_history,
            ordinary_guidelines=ordinary_guidelines,
            tool_enabled_guidelines=tool_enabled_guidelines,
            staged_events=staged_events,
        )

        response_message = await self._generate_response_message(prompt)

        return [
            ProducedEvent(
                source="server",
                type=Event.MESSAGE_TYPE,
                data={"message": response_message},
            )
        ]

    def _format_prompt(
        self,
        interaction_history: Iterable[Event],
        ordinary_guidelines: Iterable[Guideline],
        tool_enabled_guidelines: dict[Guideline, Iterable[Tool]],
        staged_events: Iterable[ProducedEvent],
    ) -> str:
        interaction_events = events_to_json(interaction_history)
        staged_events_as_dict = produced_tools_events_to_dict(staged_events)
        all_guidelines = chain(ordinary_guidelines, tool_enabled_guidelines)

        rules = "\n".join(
            f"{i}) When {g.predicate}, then {g.content}"
            for i, g in enumerate(all_guidelines, start=1)
        )

        return f"""\
The following is a list of events describing a back-and-forth
interaction between you, an AI assistant, and a user: ###
{interaction_events}
###

In generating the response, you must adhere to the following rules: ###
{rules}
###

You must generate your response message to the current
(latest) state of the interaction.

For your information, here are some staged events that have just been produced,
to assist you with generating your response message while following the rules above: ###
{staged_events_as_dict}
###

Propose revisions to the message content until you are
absolutely sure that your proposed message adheres to
each and every one of the provided rules,
with regards to the interaction's latest state.
Check yourself and criticize the last revision
every time, until you are sure the message
follows all of the rules.
Ensure that each critique is unique, to avoid repeating the same
faulty content suggestion over and over again.

Produce a valid JSON object in the format according to the following example.

{{
    "revisions": [
        {{
            "content": "some proposed message content",
            "rules_followed": [
                "#1; correctly did...",
                "#3; correctly said..."
            ],
            "rules_broken": [
                "#5; didn't do...",
                "#2; didn't say..."
            ],
            "followed_all_rules": false
        }},
        ...,
        {{
            "content": "final verified message content",
            "rules_followed": [
                "#1; correctly did...",
                "#2; correctly said...",
                "#3; correctly said...",
                "#5; correctly did..."
            ],
            "rules_broken": [],
            "followed_all_rules": true
        }},
    ]
}}
"""  # noqa

    async def _generate_response_message(self, prompt: str) -> str:
        response = await self._llm_client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="gpt-4o",
            response_format={"type": "json_object"},
            temperature=0.5,
        )

        content = response.choices[0].message.content or ""

        json_content = json.loads(content)

        final_revision = json_content["revisions"][-1]

        if not final_revision["followed_all_rules"]:
            logger.warning(f"PROBLEMATIC RESPONSE: {content}")

        return str(final_revision["content"])


class ToolsEventProducer:
    def __init__(
        self,
    ) -> None:
        self._llm_client = make_llm_client("openai")
        self.tool_caller = ToolCaller()

    async def produce_events(
        self,
        interaction_history: Iterable[Event],
        ordinary_guidelines: Iterable[Guideline],
        tool_enabled_guidelines: dict[Guideline, Iterable[Tool]],
        tools: Iterable[Tool],
    ) -> Iterable[ProducedEvent]:
        if not tool_enabled_guidelines:
            return []

        produced_tool_events: list[ProducedEvent] = []

        tool_calls = await self.tool_caller.infer_tool_calls(
            interaction_history,
            ordinary_guidelines,
            tool_enabled_guidelines,
            produced_tool_events,
        )

        tool_results = await self.tool_caller.execute_tool_calls(
            tool_calls,
            tools,
        )

        if not tool_results:
            return []

        produced_tool_events.append(
            ProducedEvent(
                source="server",
                type=Event.TOOL_TYPE,
                data={"tools_result": tool_results},
            )
        )

        return produced_tool_events
