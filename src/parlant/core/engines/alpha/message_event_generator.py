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

from itertools import chain
import json
import traceback
from typing import Mapping, Optional, Sequence

from parlant.core.contextual_correlator import ContextualCorrelator
from parlant.core.agents import Agent
from parlant.core.context_variables import ContextVariable, ContextVariableValue
from parlant.core.customers import Customer
from parlant.core.engines.alpha.event_generation import EventGenerationResult
from parlant.core.nlp.generation import GenerationInfo, SchematicGenerator
from parlant.core.engines.alpha.guideline_proposition import GuidelineProposition
from parlant.core.engines.alpha.prompt_builder import PromptBuilder, BuiltInSection, SectionStatus
from parlant.core.glossary import Term
from parlant.core.emissions import EmittedEvent, EventEmitter
from parlant.core.sessions import Event
from parlant.core.common import DefaultBaseModel
from parlant.core.logging import Logger
from parlant.core.tools import ToolId


class Revision(DefaultBaseModel):
    revision_number: int
    content: str
    guidelines_followed: Optional[list[str]] = []
    guidelines_broken: Optional[list[str]] = []
    is_repeat_message: Optional[bool] = False
    followed_all_guidelines: Optional[bool] = False
    guidelines_broken_due_to_missing_data: Optional[bool] = False
    missing_data_rationale: Optional[str] = None
    guidelines_broken_only_due_to_prioritization: Optional[bool] = False
    prioritization_rationale: Optional[str] = None


class GuidelineEvaluation(DefaultBaseModel):
    number: int
    instruction: str
    evaluation: str
    adds_value: str
    data_available: str


class MessageGenerationError(Exception):
    def __init__(self, message: str = "Message generation failed") -> None:
        super().__init__(message)


class MessageEventSchema(DefaultBaseModel):
    last_message_of_customer: Optional[str]
    produced_reply: Optional[bool] = True
    rationale: str
    revisions: list[Revision]
    evaluations_for_each_of_the_provided_guidelines: Optional[list[GuidelineEvaluation]] = None


class MessageEventGenerator:
    def __init__(
        self,
        logger: Logger,
        correlator: ContextualCorrelator,
        schematic_generator: SchematicGenerator[MessageEventSchema],
    ) -> None:
        self._logger = logger
        self._correlator = correlator
        self._schematic_generator = schematic_generator

    async def generate_events(
        self,
        event_emitter: EventEmitter,
        agents: Sequence[Agent],
        customer: Customer,
        context_variables: Sequence[tuple[ContextVariable, ContextVariableValue]],
        interaction_history: Sequence[Event],
        terms: Sequence[Term],
        ordinary_guideline_propositions: Sequence[GuidelineProposition],
        tool_enabled_guideline_propositions: Mapping[GuidelineProposition, Sequence[ToolId]],
        staged_events: Sequence[EmittedEvent],
    ) -> Sequence[EventGenerationResult]:
        assert len(agents) == 1

        with self._logger.operation("Message production"):
            if (
                not interaction_history
                and not ordinary_guideline_propositions
                and not tool_enabled_guideline_propositions
            ):
                # No interaction and no guidelines that could trigger
                # a proactive start of the interaction
                self._logger.info(
                    "Skipping response; interaction is empty and there are no guidelines"
                )
                return []

            self._logger.debug(
                f"""Guidelines applied: {json.dumps([{
                    "condition": p.guideline.content.condition,
                    "action": p.guideline.content.action,
                    "rationale": p.rationale,
                    "score": p.score}
                for p in  chain(ordinary_guideline_propositions, tool_enabled_guideline_propositions.keys())], indent=2)}"""
            )

            prompt = self._format_prompt(
                agents=agents,
                context_variables=context_variables,
                customer=customer,
                interaction_history=interaction_history,
                terms=terms,
                ordinary_guideline_propositions=ordinary_guideline_propositions,
                tool_enabled_guideline_propositions=tool_enabled_guideline_propositions,
                staged_events=staged_events,
            )

            self._logger.debug(f"Message production prompt:\n{prompt}")

            last_known_event_offset = interaction_history[-1].offset if interaction_history else -1

            await event_emitter.emit_status_event(
                correlation_id=self._correlator.correlation_id,
                data={
                    "acknowledged_offset": last_known_event_offset,
                    "status": "typing",
                    "data": {},
                },
            )

            generation_attempt_temperatures = {
                0: 0.5,
                1: 1,
                2: 0.1,
            }

            last_generation_exception: Exception | None = None

            for generation_attempt in range(3):
                try:
                    generation_info, response_message = await self._generate_response_message(
                        prompt,
                        temperature=generation_attempt_temperatures[generation_attempt],
                    )

                    if response_message is not None:
                        self._logger.debug(f'Message production result: "{response_message}"')

                        event = await event_emitter.emit_message_event(
                            correlation_id=self._correlator.correlation_id,
                            data=response_message,
                        )

                        return [EventGenerationResult(generation_info, [event])]
                    else:
                        self._logger.debug("Skipping response; no response deemed necessary")
                        return [EventGenerationResult(generation_info, [])]
                except Exception as exc:
                    self._logger.warning(
                        f"Generation attempt {generation_attempt} failed: {traceback.format_exception(exc)}"
                    )
                    last_generation_exception = exc

            raise MessageGenerationError() from last_generation_exception

    def get_guideline_propositions_text(
        self,
        ordinary: Sequence[GuidelineProposition],
        tool_enabled: Mapping[GuidelineProposition, Sequence[ToolId]],
    ) -> str:
        all_propositions = list(chain(ordinary, tool_enabled))

        if not all_propositions:
            return """
In formulating your reply, you are normally required to follow a number of behavioral guidelines.
However, in this case, no special behavioral guidelines were provided. Therefore, when generating revisions,
you don't need to specifically double-check if you followed or broke any guidelines.
"""
        guidelines = []

        for i, p in enumerate(all_propositions, start=1):
            guideline = f"Guideline #{i}) When {p.guideline.content.condition}, then {p.guideline.content.action}"

            guideline += f"\n    [Priority (1-10): {p.score}; Rationale: {p.rationale}]"
            guidelines.append(guideline)

        guideline_list = "\n".join(guidelines)

        return f"""
In formulating your reply, you are required to adhere to the following behavioral guidelines,
which were determined applicable to the latest state of the interaction.
Each guideline is accompanied by a priority score indicating its significance,
and a rationale explaining why it applies.

There are a few instances in which you may choose not to adhere to a guideline if it either:
    1. Contradicts a previous request made by the customer.
    2. Contradicts another guideline of higher or equal priority.
    3. It's absolutely inappropriate given the state of the conversation.
In all other circumstances, adhere to all of the guidelines, including cases where you deem that the guideline's predicate or rational do not currently apply. 

Guidelines: ###
{guideline_list}
###
"""

    def _format_prompt(
        self,
        agents: Sequence[Agent],
        customer: Customer,
        context_variables: Sequence[tuple[ContextVariable, ContextVariableValue]],
        interaction_history: Sequence[Event],
        terms: Sequence[Term],
        ordinary_guideline_propositions: Sequence[GuidelineProposition],
        tool_enabled_guideline_propositions: Mapping[GuidelineProposition, Sequence[ToolId]],
        staged_events: Sequence[EmittedEvent],
    ) -> str:
        assert len(agents) == 1
        builder = PromptBuilder()

        builder.add_section(
            """
GENERAL INSTRUCTIONS
-----------------
You are an AI agent who is part of a system that interacts with a customer, also referred to as 'the user'. The current state of this interaction will be provided to you later in this message.
You role is to generate a reply message to the current (latest) state of the interaction, based on provided guidelines and background information.

Later in this prompt, you'll be provided with behavioral guidelines and other contextual information you must take into account when generating your response. 

"""
        )

        builder.add_agent_identity(agents[0])
        builder.add_section(
            """
TASK DESCRIPTION:
-----------------
Continue the provided interaction in a natural and human-like manner. 
Your task is to produce a response to the latest state of the interaction.
Always abide by the following general principles (note these are not the "guidelines", these are "principles"):
Principle #1) GENERAL BEHAVIOR: Make your response as human-like as possible. Be concise and avoid being overly polite when not necessary.
Principle #2) AVOID REPEATING YOURSELF: When replying— avoid repeating yourself. Instead, refer the customer to your previous answer, or choose a new approach altogether. If a conversation is looping, point that out to the customer instead of maintaining the loop.
Principle #3) DO NOT HALLUCINATE: Do not state factual information that you do not know or are not sure about. If the customer requests information you're unsure about, state that this information is not available to you.
Principle #4) OUTPUT FORMAT: In your generated reply to the user, use markdown format when applicable. 
"""
        )
        if not interaction_history or all(
            [event.kind != "message" for event in interaction_history]
        ):
            builder.add_section(
                """
The interaction with the customer has just began, and no messages were sent by either party.
If told so by a guideline or some other contextual condition, send the first message. Otherwise, do not produce a reply.
If you decide not to emit a message, output the following:
{{
    “last_message_of_customer”: None,
    "produced_reply": false,
    "rationale": "<a few words to justify why a reply was NOT produced here>",
    "revisions": []
}}
Otherwise, follow the rest of this prompt to choose the content of your response.
        """
            )

        else:
            builder.add_section("""
Since the interaction with the customer is already ongoing, always produce a reply to the customer's last message.
The only exception where you may not produce a reply is if the customer explicitly asked you not to respond to their message.
In all other cases, even if the customer is indicating that the conversation is over, you must produce a reply.
                """)

        builder.add_section(
            f"""
Propose incremental revisions to your reply, ensuring that your proposals adhere
to each and every one of the provided guidelines based on the most recent state of interaction.

Mind the priority scores assigned to each guideline, acknowledging that in some cases,
adherence to a higher-priority guideline may necessitate deviation from another.
Use your best judgment in applying prioritization.
Note too that it is permissible for the final revision to break rules IF AND ONLY IF
all of the broken rules were broken due to conscious prioritization of guidelines,
due to either (1) conflicting with another guideline, (2) contradicting a customer's request or (3) lack of necessary context or data.
If you do not fulfill a guideline, you must clearly justify your reasoning for doing so in your reply.

Continuously critique each revision to refine the reply.
Ensure each critique is unique to prevent redundancy in the revision process.

Your final output should be a JSON object documenting the entire message development process.
This document should detail how each guideline was adhered to,
instances where one guideline was prioritized over another,
situations where guidelines could not be followed due to lack of context or data,
and the rationale for each decision made during the revision process.
Additionally, mark whether your suggested response is repeating your previous message.
if your suggested response is repetitive, further revisions are needed, until the suggested response is sufficiently unique.
The exact format of this output will be provided to you at the end of this prompt.

DO NOT PRODUCE MORE THAN 5 REVISIONS. IF YOU REACH the 5th REVISION, STOP THERE.

Examine the following examples to understand your expected behavior:

EXAMPLES
-----------------
###

Example 1: A reply that took critique in a few revisions to get right: ###
{{
    “last_message_of_customer”: “<customer’s last message in the interaction>”,
    "rationale": "<a few words to justify why you decided to respond to the customer at all>",
    "evaluations_for_each_of_the_provided_guidelines": [
        {{
            "number": 1,
            "instruction": "Do this [...]",
            "evaluation": "in this situation, I am instructed to do [...]",
            "adds_value": "I didn't do it yet, so I should do it now",
            "data_available": "no particular data is needed for this"
        }},
        {{
            "number": 2,
            "instruction": "Say this [...]",
            "evaluation": "in this situation, I am instructed to say [...]",
            "adds_value": "I didn't say it yet, so I should say it now",
            "data_available": "no particular data is needed for this"
        }},
        {{
            "number": 3,
            "instruction": "Say that [...]",
            "evaluation": "in this situation, I am instructed to say [...]",
            "adds_value": "I didn't say it yet, so I should say it now",
            "data_available": "no particular data is needed for this"
        }},
        {{
            "number": 4,
            "instruction": "Do that [...]",
            "evaluation": "in this situation, I am instructed to do [...]",
            "adds_value": "I didn't do it yet, so I should do it now",
            "data_available": "no particular data is needed for this"
        }}
    ],
    "revisions": [
        {{
            "revision_number": 1,
            "content": "some proposed message content",
            "guidelines_followed": [
                "#1; correctly did...",
                "#3; correctly said..."
            ],
            "guidelines_broken": [
                "#2; didn't say...",
                "#4; didn't do..."
            ],
            "is_repeat_message": false,
            "followed_all_guidelines": false,
            "guidelines_broken_due_to_missing_data": false,
            "guidelines_broken_only_due_to_prioritization": false
        }},
        ...,
        {{
            "revision_number": 2,
            "content": "final verified message content",
            "guidelines_followed": [
                "#1; correctly did...",
                "#2; correctly said...",
                "#3; correctly said...",
                "#5; correctly did..."
            ],
            "guidelines_broken": [],
            "is_repeat_message": false,
            "followed_all_guidelines": true
        }},
    ]
}}
###

Example 2: A reply where one guideline was prioritized over another: ###
{{
    “last_message_of_customer”: “<customer’s last message in the interaction>”,
    "rationale": "<a few words to justify why you decided to respond to the customer at all>",
    "evaluations_for_each_of_the_provided_guidelines": [
        {{
            "number": 1,
            "instruction": "When the customer chooses and orders a burger, then provide it",
            "evaluation": "The customer asked for a burger with cheese, so I need to provide it to him.",
            "adds_value": "I didn't provide the burger yet, so I should do so now.",
            "data_available": "The burger choice is available in the interaction"
        }},
        {{
            "number": 2,
            "instruction": "When the customer chooses specific ingredients on the burger, only provide those ingredients if we have them fresh in stock; otherwise, reject the order."
            "evaluation": "The customer chose cheese on the burger, but all of the cheese we currently have is expired",
            "adds_value": "I must reject the order, otherwise the customer might eat bad cheese",
            "data_available": "The relevant stock availability is given in the tool calls' data"
        }}
    ],
    "revisions": [
        {{
            "revision_number": 1,
            "content": "I'd be happy to prepare your burger as soon as we restock the requested toppings.",
            "guidelines_followed": [
                "#2; upheld food quality and did not go on to preparing the burger without fresh toppings."
            ],
            "guidelines_broken": [
                "#1; did not provide the burger with requested toppings immediately due to the unavailability of fresh ingredients."
            ],
            "is_repeat_message": false,
            "followed_all_guidelines": false,
            "guidelines_broken_only_due_to_prioritization": true,
            "prioritization_rationale": "Given the higher priority score of guideline 2, maintaining food quality standards before serving the burger is prioritized over immediate service.",
            "guidelines_broken_due_to_missing_data": false
        }}
    ]
}}
###


Example 3: Non-Adherence Due to Missing Data: ###
{{
    “last_message_of_customer”: “<customer’s last message in the interaction>”,
    "rationale": "<a few words to justify why you decided to respond to the customer at all>",
    "evaluations_for_each_of_the_provided_guidelines": [
        {{
            "number": 1,
            "instruction": "When the customer asks for a drink, check the menu and offer what's on it"
            "evaluation": "The customer did ask for a drink, so I should check the menu to see what's available.",
            "adds_value": "The customer doesn't know what drinks we have yet, so I should tell him.",
            "data_available": "No, I don't have the menu info in the interaction or tool calls"
        }}
    ],
    "revisions": [
        {{
            "revision_number": 1,
            "content": "I'm sorry, I am unable to provide this information at this time.",
            "guidelines_followed": [
            ],
            "guidelines_broken": [
                "#1; Lacking menu data in the context prevented me from providing the client with drink information."
            ],
            "is_repeat_message": false,
            "followed_all_guidelines": false,
            "missing_data_rationale": "Menu data was missing",
            "guidelines_broken_due_to_missing_data": true,
            "guidelines_broken_only_due_to_prioritization": false
        }}
    ]
}}
###


Example 4: Avoiding repetitive responses. Given that the previous response by the agent was "I'm sorry, could you please clarify your request?": ###
{{
    “last_message_of_customer”: “This is not what I was asking for”,
    "rationale": "<a few words to justify why you decided to respond to the customer at all>",
    "evaluations_for_each_of_the_provided_guidelines": [],
    "revisions": [
        {{
            "revision_number": 1,
            "content": "I apologize for the confusion. Could you please explain what I'm missing?",
            "guidelines_followed": [
            ],
            "guidelines_broken": [
            ],
            "is_repeat_message": true,
            "followed_all_guidelines": true,
        }},
        {{
            "revision_number": 2,
            "content": "I see. What am I missing?",
            "guidelines_followed": [
            ],
            "guidelines_broken": [
            ],
            "is_repeat_message": true,
            "followed_all_guidelines": true,
        }},
        {{
            "revision_number": 3,
            "content": "It seems like I'm failing to assist you with your issue. I suggest emailing our support team for further assistance.",
            "guidelines_followed": [
            ],
            "guidelines_broken": [
            ],
            "is_repeat_message": false,
            "followed_all_guidelines": true,
        }}
    ]
}}
###
"""  # noqa
        )
        builder.add_context_variables(context_variables)
        builder.add_glossary(terms)
        builder.add_section(
            self.get_guideline_propositions_text(
                ordinary_guideline_propositions,
                tool_enabled_guideline_propositions,
            ),
            name=BuiltInSection.GUIDELINE_DESCRIPTIONS,
            status=SectionStatus.ACTIVE
            if ordinary_guideline_propositions or tool_enabled_guideline_propositions
            else SectionStatus.PASSIVE,
        )
        builder.add_interaction_history(interaction_history)
        builder.add_staged_events(staged_events)
        builder.add_section(
            f"""
Produce a valid JSON object in the following format: ###

{self._get_output_format(interaction_history, list(chain(ordinary_guideline_propositions, tool_enabled_guideline_propositions)))}"""
        )

        prompt = builder.build()
        with open("message prompt.txt", "w") as f:
            f.write(prompt)
        return prompt

    def _get_output_format(
        self, interaction_history: Sequence[Event], guidelines: Sequence[GuidelineProposition]
    ) -> str:
        last_customer_message = next(
            (
                event.data["message"]
                for event in reversed(interaction_history)
                if (
                    event.kind == "message"
                    and event.source == "customer"
                    and isinstance(event.data, dict)
                )
            ),
            "",
        )
        guidelines_output_format = "\n".join(
            [
                f"""
                {{
                    "number": {i},
                    "instruction": "{g.guideline.content.action}"
                    "evaluation": "<your evaluation of the guideline to the present state of the interaction>",
                    "adds_value": "<your assessment if and to what extent following this guideline now would add value>",
                    "data_available": "<explanation whether you are provided with the required data to follow this guideline now>"
                }},"""
                for i, g in enumerate(guidelines, start=1)
            ]
        )

        return f"""
        {{
            “last_message_of_customer”: “{last_customer_message}”,
            "rationale": "<a few words to explain why you should or shouldn't produce a reply to the customer in this case>",
            "produced_reply": <BOOL>,
            "evaluations_for_each_of_the_provided_guidelines": [
{guidelines_output_format}
            ],
            "revisions": [
            {{
                "revision_number": 1,
                "content": <response chosen after revision 1>,
                "guidelines_followed": <list of guidelines that were followed>,
                "guidelines_broken": <list of guidelines that were broken>,
                "is_repeat_message": <BOOL, indicating whether "content" is a repeat of a previous message by the agent>,
                "followed_all_guidelines": <BOOL>,
                "guidelines_broken_due_to_missing_data": <BOOL, optional. Necessary only if guidelines_broken_only_due_to_prioritization is true>,
                "missing_data_rationale": <STR, optional. Necessary only if guidelines_broken_due_to_missing_data is true>,
                "guidelines_broken_only_due_to_prioritization": <BOOL, optional. Necessary only if followed_all_guidelines is true>,
                "prioritization_rationale": <STR, optional. Necessary only if guidelines_broken_only_due_to_prioritization is true>,
            }},
            ...
            ]
        }}
        ###"""

    async def _generate_response_message(
        self,
        prompt: str,
        temperature: float,
    ) -> tuple[GenerationInfo, Optional[str]]:
        message_event_response = await self._schematic_generator.generate(
            prompt=prompt,
            hints={"temperature": temperature},
        )

        if not message_event_response.content.produced_reply:
            self._logger.debug(f"MessageEventProducer produced no reply: {message_event_response}")
            return message_event_response.info, None

        if message_event_response.content.evaluations_for_each_of_the_provided_guidelines:
            self._logger.debug(
                "MessageEventGenerator guideline evaluations: "
                f"{json.dumps([e.model_dump(mode='json') for e in message_event_response.content.evaluations_for_each_of_the_provided_guidelines], indent=2)}"
            )

        self._logger.debug(
            "MessageEventGenerator revisions: "
            f"{json.dumps([r.model_dump(mode='json') for r in message_event_response.content.revisions], indent=2)}"
        )

        if first_correct_revision := next(
            (
                r
                for r in message_event_response.content.revisions
                if not r.is_repeat_message
                and (
                    r.followed_all_guidelines
                    or r.guidelines_broken_only_due_to_prioritization
                    or r.guidelines_broken_due_to_missing_data
                )
            ),
            None,
        ):
            # Sometimes the LLM continues generating revisions even after
            # it generated a correct one. Those next revisions tend to be
            # faulty, as they do not handle prioritization well. This is a workaround.
            final_revision = first_correct_revision
        else:
            final_revision = message_event_response.content.revisions[-1]

        if (
            not final_revision.followed_all_guidelines
            and not final_revision.guidelines_broken_only_due_to_prioritization
            and not final_revision.is_repeat_message
        ):
            self._logger.warning(
                f"PROBLEMATIC MESSAGE EVENT PRODUCER RESPONSE: {final_revision.content}"
            )

        return message_event_response.info, str(final_revision.content)
