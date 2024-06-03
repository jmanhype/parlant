from itertools import chain
import json
from typing import Iterable
from loguru import logger

from emcie.server.core.tools import Tool
from emcie.server.engines.alpha.tool_calls import ToolCaller
from emcie.server.engines.alpha.utils import (
    events_to_json,
    make_llm_client,
    produced_tools_events_to_json,
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
        guidelines_without_tools: Iterable[Guideline],
        guidelines_with_tools: dict[Guideline, Iterable[Tool]],
        tools: Iterable[Tool],
    ) -> Iterable[ProducedEvent]:
        tool_events = await self.tool_event_producer.produce_events(
            interaction_history,
            guidelines_without_tools,
            guidelines_with_tools,
            tools,
        )

        message_events = await self.message_event_producer.produce_events(
            interaction_history,
            guidelines_without_tools,
            guidelines_with_tools,
            tool_events,
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
        guidelines_without_tools: Iterable[Guideline],
        guidelines_with_tools: dict[Guideline, Iterable[Tool]],
        staged_events: Iterable[ProducedEvent],
    ) -> Iterable[ProducedEvent]:
        prompt = self._format_prompt(
            interaction_history=interaction_history,
            guidelines_without_tools=guidelines_without_tools,
            staged_events=staged_events,
            guidelines_with_tools=guidelines_with_tools,
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
        guidelines_without_tools: Iterable[Guideline],
        guidelines_with_tools: dict[Guideline, Iterable[Tool]],
        staged_events: Iterable[ProducedEvent],
    ) -> str:
        interaction_events = events_to_json(interaction_history)
        functions_events = produced_tools_events_to_json(staged_events)
        all_guidelines = chain(guidelines_without_tools, guidelines_with_tools)

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

For your information, here are some staged events, to assist you with
generating your response message while following the rules above: ###
{functions_events}
###

Propose revisions to the message content until you are
absolutely sure that your proposed message adheres to
each and every one of the provided rules,
with regards to the interaction's latest state.
Check yourself and criticize the last revision
every time, until you are sure the message
follows all of the rules.

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
    # TODO: consequential feature
    def __init__(
        self,
    ) -> None:
        self._llm_client = make_llm_client("openai")
        self.tool_caller = ToolCaller()

    async def produce_events(
        self,
        interaction_history: Iterable[Event],
        guidelines: Iterable[Guideline],
        guidelines_tools_associations: dict[Guideline, Iterable[Tool]],
        tools: Iterable[Tool],
    ) -> Iterable[ProducedEvent]:

        produced_tool_events: list[ProducedEvent] = []
        if not guidelines_tools_associations:
            return produced_tool_events

        max_tools_steps_count_down = 2

        while max_tools_steps_count_down:
            tools_result = await self.tool_caller.list_tools_result(
                interaction_history,
                guidelines,
                tools,
                guidelines_tools_associations,
                produced_tool_events,
            )

            if not tools_result:
                break

            produced_tool_events.append(
                ProducedEvent(
                    source="server",
                    type=Event.TOOL_TYPE,
                    data={"tools_result": tools_result},
                )
            )
            max_tools_steps_count_down -= 1

        return produced_tool_events
