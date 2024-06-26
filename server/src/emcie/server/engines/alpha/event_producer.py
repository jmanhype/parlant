from itertools import chain
import json
from typing import Iterable, Optional
from loguru import logger

from emcie.server.core.context_variables import ContextVariable, ContextVariableValue
from emcie.server.core.tools import Tool
from emcie.server.engines.alpha.guideline_filter import RetrievedGuideline
from emcie.server.engines.alpha.tool_caller import ToolCaller, produced_tools_events_to_dict
from emcie.server.engines.alpha.utils import (
    context_variables_to_json,
    events_to_json,
    make_llm_client,
)
from emcie.server.engines.common import ProducedEvent
from emcie.server.core.guidelines import Guideline
from emcie.server.core.sessions import Event


class EventProducer:

    def __init__(self) -> None:
        self.tool_event_producer = ToolEventProducer()
        self.message_event_producer = MessageEventProducer()

    async def produce_events(
        self,
        context_variables: Iterable[tuple[ContextVariable, ContextVariableValue]],
        interaction_history: Iterable[Event],
        ordinary_retrieved_guidelines: Iterable[RetrievedGuideline],
        tool_enabled_retrieved_guidelines: dict[RetrievedGuideline, Iterable[Tool]],
    ) -> Iterable[ProducedEvent]:
        interaction_event_list = list(interaction_history)
        context_variable_list = list(context_variables)

        tool_events = await self.tool_event_producer.produce_events(
            context_variables=context_variable_list,
            interaction_history=interaction_event_list,
            ordinary_retrieved_guidelines=[r.guideline for r in ordinary_retrieved_guidelines],
            tool_enabled_guidelines={
                r.guideline: tools for r, tools in tool_enabled_retrieved_guidelines.items()
            },
        )

        message_events = await self.message_event_producer.produce_events(
            context_variables=context_variable_list,
            interaction_history=interaction_event_list,
            ordinary_retrieved_guidelines=ordinary_retrieved_guidelines,
            tool_enabled_guidelines=tool_enabled_retrieved_guidelines,
            staged_events=tool_events,
        )

        return chain(tool_events, message_events)


class MessageEventProducer:
    def __init__(
        self,
    ) -> None:
        self._llm_client = make_llm_client("openai")

    async def produce_events(
        self,
        context_variables: list[tuple[ContextVariable, ContextVariableValue]],
        interaction_history: list[Event],
        ordinary_retrieved_guidelines: Iterable[RetrievedGuideline],
        tool_enabled_guidelines: dict[RetrievedGuideline, Iterable[Tool]],
        staged_events: Iterable[ProducedEvent],
    ) -> Iterable[ProducedEvent]:
        interaction_event_list = list(interaction_history)

        if (
            not interaction_event_list
            and not ordinary_retrieved_guidelines
            and not tool_enabled_guidelines
        ):
            # No interaction and no guidelines that could trigger
            # a proactive start of the interaction
            return []

        prompt = self._format_prompt(
            context_variables=context_variables,
            interaction_history=interaction_history,
            ordinary_guidelines=ordinary_retrieved_guidelines,
            tool_enabled_guidelines=tool_enabled_guidelines,
            staged_events=staged_events,
        )

        if response_message := await self._generate_response_message(prompt):
            return [
                ProducedEvent(
                    source="server",
                    type=Event.MESSAGE_TYPE,
                    data={"message": response_message},
                )
            ]

        return []

    def _format_prompt(
        self,
        context_variables: list[tuple[ContextVariable, ContextVariableValue]],
        interaction_history: list[Event],
        ordinary_guidelines: Iterable[RetrievedGuideline],
        tool_enabled_guidelines: dict[RetrievedGuideline, Iterable[Tool]],
        staged_events: Iterable[ProducedEvent],
    ) -> str:
        interaction_events_json = events_to_json(interaction_history)
        context_values = context_variables_to_json(context_variables)
        staged_events_as_dict = produced_tools_events_to_dict(staged_events)
        all_retrieved_guidelines = chain(ordinary_guidelines, tool_enabled_guidelines)

        rules = "\n".join(
            f"{i}) When {r.guideline.predicate}, then {r.guideline.content}"
            for i, r in enumerate(all_retrieved_guidelines, start=1)
        )

        prompt = ""

        if interaction_history:
            prompt += f"""\
The following is a list of events describing a back-and-forth
interaction between you, an AI assistant, and a user: ###
{interaction_events_json}
###
"""
        else:
            prompt += """\
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

        if rules:
            prompt += f"""
In generating the response, you must adhere to the following rules: ###
{rules}
###
"""
        prompt += """
You must generate your response message to the current
(latest) state of the interaction.
"""

        if staged_events_as_dict:
            prompt += f"""
For your information, here are some staged events that have just been produced,
to assist you with generating your response message while following the rules above: ###
{staged_events_as_dict}
###
"""
        prompt += f"""
Propose revisions to the message content until you are
absolutely sure that your proposed message adheres to
each and every one of the provided rules,
with regards to the interaction's latest state.
Check yourself and criticize the last revision
every time, until you are sure the message
follows all of the rules.
Ensure that each critique is unique, to avoid repeating the same
faulty content suggestion over and over again.

Produce a valid JSON object in the format according to the following examples.

Example 1: When no response was deemed appropriate: ###
{{
    "produced_response": false,
    "rationale": "a few words to justify why a response was NOT produced here",
    "revisions": []
}}
###

Example 2: A response that took critique in a few revisions to get right: ###
{{
    "produced_response": true,
    "rationale": "a few words to justify why a response was produced here",
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
###
"""  # noqa

        return prompt

    async def _generate_response_message(self, prompt: str) -> Optional[str]:
        response = await self._llm_client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="gpt-4o",
            response_format={"type": "json_object"},
            temperature=0.5,
        )

        content = response.choices[0].message.content or ""

        json_content = json.loads(content)

        if not json_content["produced_response"]:
            return None

        final_revision = json_content["revisions"][-1]

        if not final_revision["followed_all_rules"]:
            logger.warning(f"PROBLEMATIC RESPONSE: {content}")

        return str(final_revision["content"])


class ToolEventProducer:
    def __init__(
        self,
    ) -> None:
        self._llm_client = make_llm_client("openai")
        self.tool_caller = ToolCaller()

    async def produce_events(
        self,
        context_variables: list[tuple[ContextVariable, ContextVariableValue]],
        interaction_history: list[Event],
        ordinary_retrieved_guidelines: Iterable[Guideline],
        tool_enabled_guidelines: dict[Guideline, Iterable[Tool]],
    ) -> Iterable[ProducedEvent]:
        if not tool_enabled_guidelines:
            return []

        produced_tool_events: list[ProducedEvent] = []

        tool_calls = await self.tool_caller.infer_tool_calls(
            context_variables,
            interaction_history,
            ordinary_retrieved_guidelines,
            tool_enabled_guidelines,
            produced_tool_events,
        )

        tools = chain(*tool_enabled_guidelines.values())

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
