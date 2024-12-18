# Copyright 2024 Emcie Co Ltd.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from collections import defaultdict
from dataclasses import dataclass, asdict
from itertools import chain
import json
import time
import traceback
from typing import Any, Mapping, NewType, Optional, Sequence

from parlant.core import async_utils
from parlant.core.tools import Tool, ToolContext
from parlant.core.agents import Agent
from parlant.core.common import JSONSerializable, generate_id, DefaultBaseModel
from parlant.core.context_variables import ContextVariable, ContextVariableValue
from parlant.core.nlp.generation import GenerationInfo, SchematicGenerator
from parlant.core.services.tools.service_registry import ServiceRegistry
from parlant.core.sessions import Event, ToolResult
from parlant.core.glossary import Term
from parlant.core.engines.alpha.guideline_proposition import GuidelineProposition
from parlant.core.engines.alpha.prompt_builder import PromptBuilder, BuiltInSection
from parlant.core.engines.alpha.utils import emitted_tool_events_to_dicts
from parlant.core.emissions import EmittedEvent
from parlant.core.logging import Logger
from parlant.core.tools import ToolId, ToolService

ToolCallId = NewType("ToolCallId", str)
ToolResultId = NewType("ToolResultId", str)


@dataclass(frozen=True)
class ToolEventGenerationsResult:
    generations: Sequence[GenerationInfo]
    events: Sequence[Optional[EmittedEvent]]


class ToolCallEvaluation(DefaultBaseModel):
    applicability_rationale: str
    applicability_score: int
    arguments: Optional[Mapping[str, Any]] = dict()
    same_call_is_already_staged: bool
    comparison_with_rejected_tools_including_references_to_subtleties: str
    relevant_subtleties: str
    a_more_fitting_tool_was_rejected_for_some_reason_and_potentially_despite_a_found_subtlety: bool
    better_rejected_tool_name: Optional[str] = None
    better_rejected_tool_rationale: Optional[str] = None
    should_run: bool


class ToolCallInferenceSchema(DefaultBaseModel):
    last_customer_message: Optional[str] = None
    most_recent_customer_inquiry_or_need: Optional[str] = None
    most_recent_customer_inquiry_or_need_was_already_resolved: Optional[bool] = False
    name: str
    subtleties_to_be_aware_of: str
    tool_calls_for_candidate_tool: list[ToolCallEvaluation]


@dataclass(frozen=True)
class ToolCall:
    id: ToolCallId
    tool_id: ToolId
    arguments: Mapping[str, JSONSerializable]

    def __eq__(self, value: object) -> bool:
        if isinstance(value, ToolCall):
            return bool(self.tool_id == value.tool_id and self.arguments == value.arguments)
        return False


@dataclass(frozen=True)
class ToolCallResult:
    id: ToolResultId
    tool_call: ToolCall
    result: ToolResult


@dataclass(frozen=True)
class InferenceToolCallsResult:
    total_duration: float
    batch_count: int
    batch_generations: Sequence[GenerationInfo]
    batches: Sequence[Sequence[ToolCall]]


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
    ) -> InferenceToolCallsResult:
        if not tool_enabled_guideline_propositions:
            return InferenceToolCallsResult(
                total_duration=0.0,
                batch_count=0,
                batch_generations=[],
                batches=[],
            )

        batches: dict[tuple[ToolId, Tool], list[GuidelineProposition]] = defaultdict(list)
        services: dict[str, ToolService] = {}
        for proposition, tool_ids in tool_enabled_guideline_propositions.items():
            for t_id in tool_ids:
                if t_id.service_name not in services:
                    services[t_id.service_name] = await self._service_registry.read_tool_service(
                        t_id.service_name
                    )

                batches[(t_id, await services[t_id.service_name].read_tool(t_id.tool_name))].append(
                    proposition
                )

        t_start = time.time()

        with self._logger.operation(f"Tool classification processed in {len(batches)} batches)"):
            batch_tasks = [
                self._infer_tool_call_batch(
                    agents=agents,
                    context_variables=context_variables,
                    interaction_history=interaction_history,
                    terms=terms,
                    ordinary_guideline_propositions=ordinary_guideline_propositions,
                    batch=(key[0], key[1], props),
                    reference_tools=[t for t in batches if t != key],
                    staged_events=staged_events,
                )
                for key, props in batches.items()
            ]

            batch_generations, tool_call_batches = zip(
                *(await async_utils.safe_gather(*batch_tasks))
            )

        t_end = time.time()

        return InferenceToolCallsResult(
            total_duration=t_end - t_start,
            batch_count=len(batches),
            batch_generations=batch_generations,
            batches=tool_call_batches,
        )

    async def _infer_tool_call_batch(
        self,
        agents: Sequence[Agent],
        context_variables: Sequence[tuple[ContextVariable, ContextVariableValue]],
        interaction_history: Sequence[Event],
        terms: Sequence[Term],
        ordinary_guideline_propositions: Sequence[GuidelineProposition],
        batch: tuple[ToolId, Tool, list[GuidelineProposition]],
        reference_tools: Sequence[tuple[ToolId, Tool]],
        staged_events: Sequence[EmittedEvent],
    ) -> tuple[GenerationInfo, list[ToolCall]]:
        inference_prompt = self._format_tool_call_inference_prompt(
            agents,
            context_variables,
            interaction_history,
            terms,
            ordinary_guideline_propositions,
            batch,
            reference_tools,
            staged_events,
        )

        with self._logger.operation(f"Tool classification for tool_id '{batch[0]}'"):
            generation_info, inference_output = await self._run_inference(inference_prompt)

        return generation_info, [
            ToolCall(
                id=ToolCallId(generate_id()),
                tool_id=batch[0],
                arguments=tc.arguments or {},
            )
            for tc in inference_output
            if tc.should_run
            and tc.applicability_score >= 6
            and not tc.a_more_fitting_tool_was_rejected_for_some_reason_and_potentially_despite_a_found_subtlety
        ]

    async def execute_tool_calls(
        self,
        context: ToolContext,
        tool_calls: Sequence[ToolCall],
    ) -> Sequence[ToolCallResult]:
        with self._logger.operation("Tool calls"):
            tool_results = await async_utils.safe_gather(
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
        batch: tuple[ToolId, Tool, list[GuidelineProposition]],
        reference_tools: Sequence[tuple[ToolId, Tool]],
        staged_events: Sequence[EmittedEvent],
    ) -> str:
        assert len(agents) == 1

        staged_calls = self._get_staged_calls(staged_events)

        builder = PromptBuilder()

        builder.add_section(
            """

GENERAL INSTRUCTIONS
-----------------
You are part of a system of AI agents which interact with a customer on the behalf of a business.
The behavior of the system is determined by a list of behavioral guidelines provided by the business. 
Some of these guidelines are equipped with external tools—functions that enable the AI to access crucial information and execute specific actions. 
Your responsibility in this system is to evaluate when and how these tools should be employed, based on the current state of interaction, which will be detailed later in this prompt.

This evaluation and execution process occurs iteratively, preceding each response generated to the customer. 
Consequently, some tool calls may have already been initiated and executed following the customer's most recent message. 
Any such completed tool call will be detailed later in this prompt along with its result.
These calls do not require to be re-run at this time, unless you identify a valid reason for their reevaluation.


"""
        )
        builder.add_agent_identity(agents[0])
        builder.add_section(
            f"""
-----------------
TASK DESCRIPTION
-----------------
Your task is to review the provided tool and, based on your most recent interaction with the customer, decide whether to use it. 
For the provided tool, assign a score from 1 to 10 to indicate its usefulness at this time, where a higher score indicates that the tool call should execute. 
For any tool with a score of 5 or higher, provide the arguments for activation, following the format in its description.

While doing so, take the following instructions into account:

1. You may suggest tool that don’t directly address the customer’s latest interaction but can advance the conversation to a more useful state based on function definitions.
2. Each tool may be called multiple times with different arguments.
3. Avoid calling a tool with the same arguments more than once, unless clearly justified by the interaction.
4. Ensure each tool call relies only on the immediate context and staged calls, without requiring other tools not yet invoked, to avoid dependencies.
5. Use the "should_run" argument to indicate whether a tool should be executed, meaning it has a high applicability score and either (a) has not been staged with the same arguments, or (b) was staged but needs to be re-executed.
6. If a tool needs to be applied multiple times (each with different arguments), you may include it in the output multiple times.

Produce a valid JSON object according to the following format:
```json
{{
    "last_customer_message": "<REPEAT THE LAST USER MESSAGE IN THE INTERACTION>",
    "most_recent_customer_inquiry_or_need": "<customer's inquiry or need>",
    "most_recent_customer_inquiry_or_need_was_already_resolved": <BOOL>,
    "name": "<TOOL NAME>",
    "subtleties_to_be_aware_of": "<NOTE ANY SIGNIFICANT SUBTLETIES TO BE AWARE OF WHEN RUNNING THIS TOOL IN OUR AGENT'S CONTEXT>",
    "tool_calls_for_candidate_tool": [
        {{
            "applicability_rationale": "<A FEW WORDS THAT EXPLAIN WHETHER AND HOW THE TOOL NEEDS TO BE CALLED>",
            "applicability_score": <INTEGER FROM 1 TO 10>,
            "arguments": <ARGUMENTS FOR THE TOOL. CAN BE DROPPED IF THE TOOL SHOULD NOT EXECUTE>,
            "same_call_is_already_staged": <BOOLEAN>,
            "comparison_with_rejected_tools_including_references_to_subtleties": "<A VERY BRIEF OVERVIEW OF HOW THIS CALL FARES AGAINST OTHER TOOLS IN APPLICABILITY>",
            "relevant_subtleties": "<IF SUBTLETIES FOUND, REFER TO THE RELEVANT ONES HERE>",
            "a_more_fitting_tool_was_rejected_for_some_reason_and_potentially_despite_a_found_subtlety": <BOOLEAN>,
            "better_rejected_tool_name": "<IF CANDIDATE TOOL IS A WORSE FIT THAN A REJECTED TOOL, THIS IS THE NAME OF THAT REJECTED TOOL>",
            "better_rejected_tool_rationale": "<IF CANDIDATE TOOL IS A WORSE FIT THAN A REJECTED TOOL, THIS EXPLAINS WHY>",
            "should_run": <BOOL>
        }}
        ...
    ]
}}
```

where the tool provided to you under appears at least once in "tool_calls_for_candidate_tool", whether you decide to use it or not.
The exact format of your output will be provided to you at the end of this prompt.

The following examples show correct outputs for various hypothetical situations. 
Only the responses are provided, without the interaction history or tool descriptions, though these can be inferred from the responses.

EXAMPLES
-----------------
###
Example 1:

Context - the id of the customer is 12345, and check_balance(12345) is already listed as a staged tool call
###
```json
{{
    "last_customer_message": "Do I have enough money in my account to get a taxi from New York to Newark?",
    "most_recent_customer_inquiry_or_need": "Checking customer's balance, comparing it to the price of a taxi from New York to Newark, and report the result to the customer",
    "most_recent_customer_inquiry_or_need_was_already_resolved": false,
    "name": "check_balance",
    "subtleties_to_be_aware_of": "<NOTE ANY SIGNIFICANT SUBTLETIES TO BE AWARE OF WHEN RUNNING THIS TOOL IN OUR AGENT'S CONTEXT>",
    "tool_calls_for_candidate_tool": [
        {{
            "applicability_rationale": "We need the client's current balance to respond to their question",
            "applicability_score": 9,
            "arguments": {{
                "customer_id": "12345",
            }},
            "same_call_is_already_staged": true,
            "comparison_with_rejected_tools_including_references_to_subtleties": "There are no tools in the list of rejected tools",
            "relevant_subtleties": "<IF SUBTLETIES FOUND, REFER TO THE RELEVANT ONES HERE>",
            "a_more_fitting_tool_was_rejected_for_some_reason_and_potentially_despite_a_found_subtlety": false,
            "should_run": false
        }}
    ]
}}
```

###
Example 2:

Context - the id of the customer is 12345, and check_balance(12345) is listed as the only staged tool call
###
```json
{{
    "last_customer_message": "Do I have enough money in my account to get a taxi from New York to Newark?",
    "most_recent_customer_inquiry_or_need": "Checking customer's balance, comparing it to the price of a taxi from New York to Newark, and report the result to the customer",
    "most_recent_customer_inquiry_or_need_was_already_resolved": false,
    "name": "ping_supervisor",
    "subtleties_to_be_aware_of": "<NOTE ANY SIGNIFICANT SUBTLETIES TO BE AWARE OF WHEN RUNNING THIS TOOL IN OUR AGENT'S CONTEXT>",
    "tool_calls_for_candidate_tool": [
        {{
            
            "applicability_rationale": "There is no reason to notify the supervisor of anything",
            "applicability_score": 1,
            "same_call_is_already_staged": false,
            "comparison_with_rejected_tools_including_references_to_subtleties": "There are no tools in the list of rejected tools",
            "relevant_subtleties": "<IF SUBTLETIES FOUND, REFER TO THE RELEVANT ONES HERE>",
            "a_more_fitting_tool_was_rejected_for_some_reason_and_potentially_despite_a_found_subtlety": false,
            "should_run": false
        }}
    ]
}}
```

###
Example 3:

Context - the id of the customer is 12345, and check_balance(12345) is the only staged tool call, assume some irrelevant reference tools exists
###
```json
{{
    "last_customer_message": "Do I have enough money in my account to get a taxi from New York to Newark?",
    "most_recent_customer_inquiry_or_need": "Checking customer's balance, comparing it to the price of a taxi from New York to Newark, and report the result to the customer",
    "most_recent_customer_inquiry_or_need_was_already_resolved": false,
    "name": "check_ride_price",
    "subtleties_to_be_aware_of": "<NOTE ANY SIGNIFICANT SUBTLETIES TO BE AWARE OF WHEN RUNNING THIS TOOL IN OUR AGENT'S CONTEXT>",
    "tool_calls_for_candidate_tool": [
        {{
            "applicability_rationale": "We need to know the price of a ride from New York to Newark to respond to the customer",
            "applicability_score": 9,
            "arguments": {{
                "origin": "New York",
                "Destination": "Newark",
            }},
            "same_call_is_already_staged": false,
            "comparison_with_rejected_tools_including_references_to_subtleties": "None of the available reference tools are deemed more suitable for the candidate tool’s application",
            "relevant_subtleties": "<IF SUBTLETIES FOUND, REFER TO THE RELEVANT ONES HERE>",
            "a_more_fitting_tool_was_rejected_for_some_reason_and_potentially_despite_a_found_subtlety": false,
            "should_run": true
        }}
    ]
}}
```

###
Example 4:
Context - the candidate tool is check_calories(<product_name>): returns the number of calories in a the product
- one reference tool of check_stock(): returns all menu items that are currently in stock
###
```json
{{
    "last_customer_message": "Which pizza has more calories, the classic margherita or the deep dish?",
    "most_recent_customer_inquiry_or_need": "Checking the number of calories in two types of pizza and replying with which one has more",
    "most_recent_customer_inquiry_or_need_was_already_resolved": false,
    "name": "check_calories",
    "subtleties_to_be_aware_of": "<NOTE ANY SIGNIFICANT SUBTLETIES TO BE AWARE OF WHEN RUNNING THIS TOOL IN OUR AGENT'S CONTEXT>",
    "tool_calls_for_candidate_tool": [
        {{
            "applicability_rationale": "We need to check how many calories are in the margherita pizza",
            "applicability_score": 9,
            "arguments": {{
                "product_name": "margherita",
            }},
            "same_call_is_already_staged": false,
            "comparison_with_rejected_tools_including_references_to_subtleties": "None of the available reference tools are deemed more suitable for the candidate tool’s application",
            "relevant_subtleties": "<IF SUBTLETIES FOUND, REFER TO THE RELEVANT ONES HERE>",
            "a_more_fitting_tool_was_rejected_for_some_reason_and_potentially_despite_a_found_subtlety": false,
            "should_run": true
            
        }},
        {{
            "applicability_rationale": "We need to check how many calories are in the deep dish pizza",
            "applicability_score": 9,
            "arguments": {{
                "product_name": "deep dish",
            }},
            "same_call_is_already_staged": false,
            "comparison_with_rejected_tools_including_references_to_subtleties": "None of the available reference tools are deemed more suitable for the candidate tool’s application",
            "relevant_subtleties": "<IF SUBTLETIES FOUND, REFER TO THE RELEVANT ONES HERE>",
            "a_more_fitting_tool_was_rejected_for_some_reason_and_potentially_despite_a_found_subtlety": false,
            "should_run": true
        }}
    ]
}}
```

###
Example 5:
Context - the candidate tool is check_vehicle_price(model: str), and reference tool of - check_motorcycle_price(model: str)
###
```json
{{
    "last_customer_message": "What's your price for a Harley-Davidson Street Glide?",
    "most_recent_customer_inquiry_or_need": "Checking the price of a Harley-Davidson Street Glide motorcycle",
    "most_recent_customer_inquiry_or_need_was_already_resolved": false,
    "name": "check_motorcycle_price",
    "subtleties_to_be_aware_of": "<NOTE ANY SIGNIFICANT SUBTLETIES TO BE AWARE OF WHEN RUNNING THIS TOOL IN OUR AGENT'S CONTEXT>",
    "tool_calls_for_candidate_tool": [
        {{
            "applicability_rationale": "we need to check for the price of a specific motorcycle model",
            "applicability_score": 9,
            "arguments": {{
                "model": "Harley-Davidson Street Glide",
            }},
            "same_call_is_already_staged": false,
            "comparison_with_rejected_tools_including_references_to_subtleties": "candidate tool is more specialized for this use case than the rejected tools",
            "relevant_subtleties": "<IF SUBTLETIES FOUND, REFER TO THE RELEVANT ONES HERE>",
            "a_more_fitting_tool_was_rejected_for_some_reason_and_potentially_despite_a_found_subtlety": false,
            "better_rejected_tool_name": "check_motorcycle_price",
            "better_rejected_tool_rationale": "the only reference tool is less relevant than the candidate tool, since the candidate tool is designed specifically for motorcycle models, and not just general vehicles.",
            "should_run": true
        }},
    ]
}}
```

###
Example 6:
Context - the candidate tool is check_motorcycle_price(model: str), and one reference tool of - check_vehicle_price(model: str)
###
```json
{{
    "last_customer_message": "What's your price for a Harley-Davidson Street Glide?",
    "most_recent_customer_inquiry_or_need": "Checking the price of a Harley-Davidson Street Glide motorcycle",
    "most_recent_customer_inquiry_or_need_was_already_resolved": false,
    "name": "check_vehicle_price",
    "subtleties_to_be_aware_of": "<NOTE ANY SIGNIFICANT SUBTLETIES TO BE AWARE OF WHEN RUNNING THIS TOOL IN OUR AGENT'S CONTEXT>",
    "tool_calls_for_candidate_tool": [
        {{
            "applicability_rationale": "we need to check for the price of a specific vehicle - a Harley-Davidson Street Glide",
            "applicability_score": 8,
            "arguments": {{
                "model": "Harley-Davidson Street Glide",
            }},
            "same_call_is_already_staged": false,
            "comparison_with_rejected_tools_including_references_to_subtleties": "not as good a fit as check_motorcycle_price",
            "relevant_subtleties": "<IF SUBTLETIES FOUND, REFER TO THE RELEVANT ONES HERE>",
            "a_more_fitting_tool_was_rejected_for_some_reason_and_potentially_despite_a_found_subtlety": true,
            "better_rejected_tool_name": "check_motorcycle_price",
            "better_rejected_tool_rationale": "check_motorcycle_price applies specifically for motorcycles, which is better fitting for this case compared to the more general check_vehicle_price",
            "should_run": false
        }},
    ]
}}
```
###
Example 7:
Context - the candidate tool is check_indoor_temperature(room: str), and reference tool of check_temperature(location: str, type: str)
###
```json
{{
    "last_customer_message": "What's the temperature in the living room right now?",
    "most_recent_customer_inquiry_or_need": "Checking the current temperature in the living room",
    "most_recent_customer_inquiry_or_need_was_already_resolved": false,
    "name": "check_indoor_temperature",
    "subtleties_to_be_aware_of": "<NOTE ANY SIGNIFICANT SUBTLETIES TO BE AWARE OF WHEN RUNNING THIS TOOL IN OUR AGENT'S CONTEXT>",
    "tool_calls_for_candidate_tool": [
        {{
            "applicability_rationale": "need to check the current temperature in a specific room",
            "applicability_score": 7,
            "arguments": {{
                "room": "living room"
            }},
            "same_call_is_already_staged": false,
            "comparison_with_rejected_tools_including_references_to_subtleties": "not as good a fit as check_temperature",
            "relevant_subtleties": "<IF SUBTLETIES FOUND, REFER TO THE RELEVANT ONES HERE>",
            "a_more_fitting_tool_was_rejected_for_some_reason_and_potentially_despite_a_found_subtlety": true,
            "better_rejected_tool_name": "check_temperature",
            "better_rejected_tool_rationale": "check_temperature is more versatile and can handle both indoor and outdoor locations with the type parameter, making it more suitable than the room-specific tool",
            "should_run": false
        }}
    ]
}}
```

###
Example 8:
Context - the candidate tool is search_product(query: str), and reference tool of search_electronics(query: str, specifications: dict)
###
```json
{{
    "last_customer_message": "I'm looking for a gaming laptop with at least 16GB RAM and an RTX 3080",
    "most_recent_customer_inquiry_or_need": "Searching for a gaming laptop with specific technical requirements",
    "most_recent_customer_inquiry_or_need_was_already_resolved": false,
    "name": "search_product",
    "subtleties_to_be_aware_of": "<NOTE ANY SIGNIFICANT SUBTLETIES TO BE AWARE OF WHEN RUNNING THIS TOOL IN OUR AGENT'S CONTEXT>",
    "tool_calls_for_candidate_tool": [
        {{
            "applicability_rationale": "need to search for a product with specific technical requirements",
            "applicability_score": 6,
            "arguments": {{
                "query": "gaming laptop RTX 3080 16GB RAM"
            }},
            "same_call_is_already_staged": false,
            "comparison_with_rejected_tools_including_references_to_subtleties": "not as good a fit as search_electronics",
            "relevant_subtleties": "<IF SUBTLETIES FOUND, REFER TO THE RELEVANT ONES HERE>",
            "a_more_fitting_tool_was_rejected_for_some_reason_and_potentially_despite_a_found_subtlety": true,
            "better_rejected_tool_name": "search_electronics",
            "better_rejected_tool_rationale": "search_electronics is more appropriate as it allows for structured specification of technical requirements rather than relying on text search, which will provide more accurate results for electronic products",
            "should_run": false
        }}
    ]
}}
```
"""  # noqa
        )
        builder.add_context_variables(context_variables)
        builder.add_glossary(terms)
        builder.add_interaction_history(interaction_event_list)

        builder.add_section(
            self._add_guideline_propositions_section(
                ordinary_guideline_propositions,
                (batch[0], batch[2]),
            ),
            name=BuiltInSection.GUIDELINE_DESCRIPTIONS,
        )
        builder.add_section(
            self._add_tool_definitions_section(
                candidate_tool=(batch[0], batch[1]),
                reference_tools=reference_tools,
            )
        )
        if staged_calls:
            builder.add_section(
                f"""
STAGED TOOL CALLS
-----------------
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

        builder.add_section(
            f"""
OUTPUT FORMAT
-----------------
Given the tool, your output should adhere to the following format:
```json
{{
    "last_customer_message": "<REPEAT THE LAST USER MESSAGE IN THE INTERACTION>",
    "most_recent_customer_inquiry_or_need": "<customer's inquiry or need>",
    "most_recent_customer_inquiry_or_need_was_already_resolved": <BOOL>,
    "name": "{batch[0].service_name}:{batch[0].tool_name}",
    "subtleties_to_be_aware_of": "<NOTE ANY SIGNIFICANT SUBTLETIES TO BE AWARE OF WHEN RUNNING THIS TOOL IN OUR AGENT'S CONTEXT>",
    "tool_calls_for_candidate_tool": [
        {{
            "applicability_rationale": "<A FEW WORDS THAT EXPLAIN WHETHER, HOW, AND TO WHAT EXTENT THE TOOL NEEDS TO BE CALLED AT THIS POINT>",
            "applicability_score": <INTEGER FROM 1 TO 10>,
            "arguments": <ARGUMENTS FOR THE TOOL. CAN BE OMITTED IF THE TOOL SHOULD NOT EXECUTE>,
            "same_call_is_already_staged": <BOOLEAN>,
            "comparison_with_rejected_tools_including_references_to_subtleties": "<A VERY BRIEF OVERVIEW OF HOW THIS CALL FARES AGAINST OTHER TOOLS IN APPLICABILITY>",
            "relevant_subtleties": "<IF SUBTLETIES FOUND, REFER TO THE RELEVANT ONES HERE>",
            "a_more_fitting_tool_was_rejected_for_some_reason_and_potentially_despite_a_found_subtlety": <BOOLEAN>,
            "better_rejected_tool_name": "<IF CANDIDATE TOOL IS A WORSE FIT THAN A REJECTED TOOL, THIS IS THE NAME OF THAT REJECTED TOOL>",
            "better_rejected_tool_rationale": "<IF CANDIDATE TOOL IS A WORSE FIT THAN A REJECTED TOOL, THIS EXPLAINS WHY>",
            "should_run": <BOOL>
        }}                                               
    ]
}}
```

However, note that you may choose to have multiple entries in 'tool_calls_for_candidate_tool' if you wish to call the candidate tool multiple times with different arguments.
###
        """
        )

        return builder.build()

    def _add_tool_definitions_section(
        self, candidate_tool: tuple[ToolId, Tool], reference_tools: Sequence[tuple[ToolId, Tool]]
    ) -> str:
        def _get_tool_spec(t_id: ToolId, t: Tool) -> dict[str, Any]:
            return {
                "name": t_id.to_string(),
                "description": t.description,
                "parameters": t.parameters,
                "required_parameters": t.required,
            }

        candidate_tool_spec = _get_tool_spec(candidate_tool[0], candidate_tool[1])
        if not reference_tools:
            return f"""
The following is the tool function definition.
IMPORTANT: You must not return results for any tool other than this one, even if you believe they might be relevant:
###
{candidate_tool_spec}
###
"""
        else:
            reference_tool_specs = [
                _get_tool_spec(tool_id, tool) for tool_id, tool in reference_tools
            ]
            return f"""
You are provided with multiple tools, categorized as follows:
- Candidate Tool: The tool under your evaluation.
- Rejected Tools: A list of additional tools that have been considered already and deemed irrelevant for an unspecified reason

Your task is to evaluate the necessity and usage of the Candidate Tool ONLY.
- Use the Rejected Tools as a contextual benchmark to decide whether the Candidate Tool should be run.
The rejected tools may have been rejected for any reason whatsoever, which you are not privy to.
If the Candidate Tool seems even less relevant than any of the Rejected Tools, then it should not be run at all.
DO NOT RUN the Candidate Tool as a "FALLBACK", "LAST RESORT", or "LAST VIABLE CHOICE" if another tool that actually seems more appropriate was nonetheless rejected for some reason.
Remember that other tools were rejected while taking your (agent's) description and glossary into full consideration. Nothing was overlooked.
However, if the Candidate Tool truly offers a unique advantage or capability over all other Rejected Tools,
given the agent's description and glossary, then do choose to use it and provide its arguments. 
Finally, focus solely on evaluating the Candidate Tool; do not evaluate any other tool.

Rejected tools: ###
{reference_tool_specs}
###

Candidate tool: ###
{candidate_tool_spec}
###
"""

    def _add_guideline_propositions_section(
        self,
        ordinary_guideline_propositions: Sequence[GuidelineProposition],
        tool_id_propositions: tuple[ToolId, list[GuidelineProposition]],
    ) -> str:
        all_propositions = list(chain(ordinary_guideline_propositions, tool_id_propositions[1]))

        if all_propositions:
            guidelines = []

            for i, p in enumerate(all_propositions, start=1):
                guideline = (
                    f"{i}) When {p.guideline.content.condition}, then {p.guideline.content.action}"
                )
                guidelines.append(guideline)

            guideline_list = "\n".join(guidelines)
        return f"""
GUIDELINES
---------------------
The following guidelines have been identified as relevant to the current state of interaction with the customer. 
Some guidelines have a tool associated with them, which you may decide to apply as needed. Use these guidelines to understand the context for the provided tool.

Guidelines: 
###
{guideline_list}
\n    Associated Tool: {tool_id_propositions[0].service_name}:{tool_id_propositions[0].tool_name}"
###
"""

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
            hints={"temperature": 0.0},
        )

        log_message = json.dumps(inference.content.model_dump(mode="json"), indent=2)

        self._logger.debug(f"Tool call request results: {log_message}")

        return inference.info, inference.content.tool_calls_for_candidate_tool

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
