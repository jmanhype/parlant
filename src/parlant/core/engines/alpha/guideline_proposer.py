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

import asyncio
from dataclasses import dataclass
from functools import cached_property
from itertools import chain
import json
import math
import time
from typing import Optional, Sequence

from parlant.core.agents import Agent
from parlant.core.context_variables import ContextVariable, ContextVariableValue
from parlant.core.customers import Customer
from parlant.core.nlp.generation import GenerationInfo, SchematicGenerator
from parlant.core.engines.alpha.guideline_proposition import GuidelineProposition
from parlant.core.engines.alpha.prompt_builder import BuiltInSection, PromptBuilder, SectionStatus
from parlant.core.glossary import Term
from parlant.core.guidelines import Guideline
from parlant.core.sessions import Event
from parlant.core.emissions import EmittedEvent
from parlant.core.common import DefaultBaseModel
from parlant.core.logging import Logger


# TODO change condition back to predicate. Change user to customer.
class GuidelinePropositionSchema(DefaultBaseModel):
    condition_number: int
    condition: str
    condition_application_rationale: str
    condition_applies: bool
    action: str
    guideline_previously_applied_rationale: Optional[str] = ""
    guideline_previously_applied: Optional[bool] = False
    guideline_should_reapply: Optional[bool] = False
    applies_score: int


class GuidelinePropositionsSchema(DefaultBaseModel):
    checks: Sequence[GuidelinePropositionSchema]


@dataclass(frozen=True)
class ConditionApplicabilityEvaluation:
    guideline_number: int
    condition: str
    action: str
    score: int
    condition_application_rationale: str
    guideline_previously_applied_rationale: str


@dataclass(frozen=True)
class GuidelinePropositionResult:
    total_duration: float
    batch_count: int
    batch_generations: Sequence[GenerationInfo]
    batches: Sequence[Sequence[GuidelineProposition]]

    @cached_property
    def propositions(self) -> Sequence[GuidelineProposition]:
        return list(chain.from_iterable(self.batches))


class GuidelineProposer:
    def __init__(
        self,
        logger: Logger,
        schematic_generator: SchematicGenerator[GuidelinePropositionsSchema],
    ) -> None:
        self._logger = logger
        self._schematic_generator = schematic_generator

    async def propose_guidelines(
        self,
        agents: Sequence[Agent],
        customer: Customer,
        guidelines: Sequence[Guideline],
        context_variables: Sequence[tuple[ContextVariable, ContextVariableValue]],
        interaction_history: Sequence[Event],
        terms: Sequence[Term],
        staged_events: Sequence[EmittedEvent],
    ) -> GuidelinePropositionResult:
        if not guidelines:
            return GuidelinePropositionResult(
                total_duration=0.0, batch_count=0, batch_generations=[], batches=[]
            )

        t_start = time.time()
        batches = self._create_guideline_batches(
            guidelines,
            batch_size=self._get_optimal_batch_size(guidelines),
        )

        with self._logger.operation(
            f"Guideline proposal ({len(guidelines)} guidelines processed in {len(batches)} batches)"
        ):
            batch_tasks = [
                self._process_guideline_batch(
                    agents,
                    customer,
                    context_variables,
                    interaction_history,
                    staged_events,
                    terms,
                    batch,
                )
                for batch in batches
            ]

            batch_generations, condition_evaluations_batches = zip(
                *(await asyncio.gather(*batch_tasks))
            )

            propositions_batches: list[list[GuidelineProposition]] = []

            for batch in condition_evaluations_batches:  # TODO I was here fixing a bug
                guideline_propositions = []
                for evaluation in batch:
                    guideline_propositions += [
                        GuidelineProposition(
                            guideline=g, score=evaluation.score, rationale=evaluation.rationale
                        )
                        for g in guidelines[evaluation.guideline_number]
                    ]
                propositions_batches.append(guideline_propositions)

            t_end = time.time()

            return GuidelinePropositionResult(
                total_duration=t_end - t_start,
                batch_count=len(batches),
                batch_generations=batch_generations,
                batches=propositions_batches,
            )

    def _get_optimal_batch_size(self, guidelines: Sequence[Guideline]) -> int:
        guideline_n = len(guidelines)

        if guideline_n <= 10:
            return 1
        elif guideline_n <= 20:
            return 2
        elif guideline_n <= 30:
            return 3
        else:
            return 5

    def _create_guideline_batches(
        self,
        guidelines: Sequence[Guideline],
        batch_size: int,
    ) -> Sequence[Sequence[Guideline]]:
        batches = []
        batch_count = math.ceil(len(guidelines) / batch_size)

        for batch_number in range(batch_count):
            start_offset = batch_number * batch_size
            end_offset = start_offset + batch_size
            batch = guidelines[start_offset:end_offset]
            batches.append(batch)

        return batches

    async def _process_guideline_batch(
        self,
        agents: Sequence[Agent],
        customer: Customer,
        context_variables: Sequence[tuple[ContextVariable, ContextVariableValue]],
        interaction_history: Sequence[Event],
        staged_events: Sequence[EmittedEvent],
        terms: Sequence[Term],
        batch: Sequence[Guideline],
    ) -> tuple[GenerationInfo, list[ConditionApplicabilityEvaluation]]:
        prompt = self._format_prompt(
            agents,
            customer,
            context_variables=context_variables,
            interaction_history=interaction_history,
            staged_events=staged_events,
            terms=terms,
            guidelines=batch,
        )

        with self._logger.operation(f"Guideline evaluation batch ({len(batch)} guidelines)"):
            propositions_generation_response = await self._schematic_generator.generate(
                prompt=prompt,
                hints={"temperature": 0.3},
            )

        propositions = []

        for proposition in propositions_generation_response.content.checks:
            guideline = batch[int(proposition.condition_number) - 1]

            self._logger.debug(
                f'Guideline evaluation for "when {guideline.content.condition} then {guideline.content.action}":\n'  # noqa
                f'  Score: {proposition.applies_score}/10; Condition rationale: "{proposition.condition_application_rationale}"; Re-application rationale: "{proposition.guideline_previously_applied_rationale}"'
            )

            if (proposition.applies_score >= 6) and (
                not proposition.guideline_previously_applied or proposition.guideline_should_reapply
            ):
                propositions.append(
                    ConditionApplicabilityEvaluation(
                        guideline_number=proposition.condition_number,
                        condition=batch[int(proposition.condition_number) - 1].content.condition,
                        action=batch[int(proposition.condition_number) - 1].content.action,
                        score=proposition.applies_score,
                        condition_application_rationale=proposition.condition_application_rationale,
                        guideline_previously_applied_rationale=proposition.guideline_previously_applied_rationale
                        or "",
                    )
                )

        return propositions_generation_response.info, propositions

    def _format_prompt(
        self,
        agents: Sequence[Agent],
        customer: Customer,
        context_variables: Sequence[tuple[ContextVariable, ContextVariableValue]],
        interaction_history: Sequence[Event],
        staged_events: Sequence[EmittedEvent],
        terms: Sequence[Term],
        guidelines: Sequence[Guideline],
    ) -> str:
        assert len(agents) == 1

        result_structure = [
            {
                "condition_number": i,
                "condition": g.content.condition,
                "condition_application_rationale": "<Explanation for why the condition is or isn't met>",
                "condition_applies": "<BOOL>",
                "action": g.content.action,
                "guideline_previously_applied_rationale": "<Explanation for whether and how this guideline was previously applied. Optional, necessary only if the condition applied.>",
                "guideline_previously_applied": "<BOOL: Optional, whether the condition already applied and the action was already taken>",
                "guideline_should_reapply": "<BOOL: Optional, only necessary if guideline_previously_applied is true>",
                "applies_score": "<Relevance score of the guideline between 1 and 10. A higher score means that the condition applies and the action hasn't yet>",
            }
            for i, g in enumerate(guidelines, start=1)
        ]
        guidelines_text = "\n".join(
            f"{i}) condition: {g.content.condition}. action: {g.content.action}"
            for i, g in enumerate(guidelines, start=1)
        )

        builder = PromptBuilder()

        builder.add_section(
            """
GENERAL INSTRUCTIONS
-----------------
In our system, the behavior of a conversational AI agent is guided by "guidelines". The agent makes use of these guidelines whenever it interacts with a user.
Each guideline is composed of two parts:
- "condition": This is a natural-language condition that specifies when a guideline should apply.
          We look at each conversation at any particular state, and we test against this
          condition to understand if we should have this guideline participate in generating
          the next reply to the user.
- "action": This is a natural-language instruction that should be followed by the agent
          whenever the "condition" part of the guideline applies to the conversation in its particular state.
          Any instruction described here applies only to the agent, and not to the user.


Task Description
----------------
Your task is to evaluate the relevance and applicability of a set of provided 'when' conditions to the most recent state of an interaction between yourself (an AI assistant) and a user. 
These conditions, along with the interaction details, will be provided later in this message. 
For each condition that is met, determine whether its corresponding action should be taken by the agent or if it has already been addressed previously.


Process Description
-------------------
a. Examine Interaction Events: Review the provided interaction events to discern the most recent state of the interaction between the user and the assistant.
b. Evaluate Conditions: Assess the entire interaction to determine whether each condition is still relevant and directly fulfilled based on the most recent interaction state.
c. Check for Prior Action: Determine whether the condition has already been addressed, i.e., whether it applied in an earlier state and its corresponding action has already been performed.
d. Guideline Application: A guideline should be applied only if:
    (1) Its condition is currently met and its action has not been performed yet, or
    (2) The interaction warrants re-application of its action (e.g., when a recurring condition becomes true again after previously being fulfilled).

For each provided guideline, return:
    (1) Whether its condition is fulfilled.
    (2) Whether its action needs to be applied now or if it has already been performed, making it unnecessary at this time.


Insights and Clarifications
-------------------
A condition typically no longer applies if its corresponding action has already been executed. 
However, there are exceptions where re-application is warranted, such as when the condition describes a recurring user action (e.g., "the user is asking a question") and the condition becomes true again due to repetition.
In these cases, use your judgment to evaluate whether re-applying the action would result in a natural and beneficial response.

Actions indicating continuous behavior (e.g., "do not ask the user for their age") should generally be re-applied whenever their condition is met.

Actions involving singular behavior (e.g., "send the user our address") should be re-applied more conservatively. 
Only re-apply these if the condition ceased to be true earlier in the conversation before being fulfilled again in the current context.
    

Examples of Condition Evaluations:
-------------------
Example #1:
- Interaction Events: ###
[{{"id": "11", "kind": "<message>", "source": "customer",
[{{"id": "11", "kind": "<message>", "source": "customer",
"data": {{"message": "Can I purchase a subscription to your software?"}}}},
{{"id": "23", "kind": "<message>", "source": "assistant",
"data": {{"message": "Absolutely, I can assist you with that right now."}}}},
{{"id": "34", "kind": "<message>", "source": "customer",
{{"id": "34", "kind": "<message>", "source": "customer",
"data": {{"message": "Please proceed with the subscription for the Pro plan."}}}},
{{"id": "56", "kind": "<message>", "source": "assistant",
"data": {{"message": "Your subscription has been successfully activated.
Is there anything else I can help you with?"}}}},
{{"id": "78", "kind": "<message>", "source": "customer",
{{"id": "78", "kind": "<message>", "source": "customer",
"data": {{"message": "Yes, can you tell me more about your data security policies?"}}}}]
###
- Guidelines: ###
1) condition: the client initiates a purchase. action: Open a new cart for the customer
2) condition: the client asks about data security. action: Refer the customer to our privacy policy page
###
- **Expected Result**:
```json
{{ "checks": [
    {{
        "condition_number": 1,
        "condition": "the client initiates a purchase",
        "condition_application_rationale": "The purchase-related guideline was initiated earlier, but is currently irrelevant since the client completed the purchase and the conversation has moved to a new topic.",
        "condition_applies": false
        "applies_score": 3
    }},
    {{
        "condition_number": 2,
        "condition": "the client asks about data security",
        "condition_applies": true
        "condition_application_rationale": "The client specifically inquired about data security policies, making this guideline highly relevant to the ongoing discussion.",
        "action": "Refer the customer to our privacy policy page",
        "guideline_previously_applied_rationale": "This is the first time data security has been mentioned, and the user has not been referred to the privacy policy page yet",
        "guideline_previously_applied": false,
        "guideline_should_reapply": false,
        "applies_score": 9
    }}
]}}
```

"""  # noqa
        )
        builder.add_agent_identity(agents[0])
        builder.add_context_variables(context_variables)
        builder.add_glossary(terms)
        builder.add_interaction_history(interaction_history)
        builder.add_staged_events(staged_events)
        builder.add_section(
            name=BuiltInSection.GUIDELINES,
            content=f"""
- Guidelines list: ###
{guidelines_text}
###
""",
            status=SectionStatus.ACTIVE,
        )

        builder.add_section(f"""
IMPORTANT: Please note there are exactly {len(guidelines)} guidelines in the list for you to check.

Expected Output
---------------------------
- Specify the applicability of each predicate by filling in the rationale and applied score in the following list:

    ```json
    {{
        "checks":
        {json.dumps(result_structure)}
    }}
    ```""")

        prompt = builder.build()
        with open("guideline proposition prompt.txt", "w") as f:
            f.write(prompt)
        return prompt


# #### Example #2:
# [{{"id": "112", "kind": "<message>", "source": "user",
# "data": {{"message": "I need to make this quick.
# Can you give me a brief overview of your pricing plans?"}}}},
# {{"id": "223", "kind": "<message>", "source": "assistant",
# "data": {{"message": "Absolutely, I'll keep it concise. We have three main plans: Basic,
# Advanced, and Pro. Each offers different features, which I can summarize quickly for you."}}}},
# {{"id": "334", "kind": "<message>", "source": "user",
# "data": {{"message": "Tell me about the Pro plan."}}}},
# ###
# - Conditions: ###
# 1) the client indicates they are in a hurry
# 2) a client inquires about pricing plans
# 3) a client asks for a summary of the features of the three plans.
# ###
# - **Expected Result**:
# ```json
# {{
#     "checks": [
#         {{
#             "condition_number": 1,
#             "condition": "the client indicates they are in a hurry",
#             "you_the_agent_already_resolved_this_according_to_the_record_of_the_interaction": false,
#             "is_this_condition_hard_or_tricky_to_confidently_ascertain": true,
#             "rationale": "The client initially stated they were in a hurry. This urgency applies throughout the conversation unless stated otherwise.",
#             "applies_score": 8
#         }},
#         {{
#             "condition_number": 2,
#             "condition": "a client inquires about pricing plans",
#             "you_the_agent_already_resolved_this_according_to_the_record_of_the_interaction": false,
#             "is_this_condition_hard_or_tricky_to_confidently_ascertain": true,
#             "rationale": "The client inquired about pricing plans, specifically asking for details about the Pro plan.",
#             "applies_score": 9
#         }},
#         {{
#             "condition_number": 3,
#             "condition": "a client asks for a summary of the features of the three plans.",
#             "you_the_agent_already_resolved_this_according_to_the_record_of_the_interaction": false,
#             "rationale": "The plan summarization guideline is irrelevant since the client only asked about the Pro plan.",
#             "applies_score": 2
#         }},
#     ]
# }}
# ```
# ### Example #3:
# - Interaction Events: ###
# [{{"id": "13", "kind": "<message>", "source": "user",
# "data": {{"message": "Can you recommend a good science fiction movie?"}}}},
# {{"id": "14", "kind": "<message>", "source": "assistant",
# "data": {{"message": "Sure, I recommend 'Inception'. It's a great science fiction movie."}}}},
# {{"id": "15", "kind": "<message>", "source": "user",
# "data": {{"message": "Thanks, I'll check it out."}}}}]
# ###
# - Conditions: ###
# 1) the client asks for a recommendation
# 2) the client asks about movie genres
# ###
# - **Expected Result**:
# ```json
# {{
#     "checks": [
#         {{
#             "condition_number": "1",
#             "condition": "the client asks for a recommendation",
#             "you_the_agent_already_resolved_this_according_to_the_record_of_the_interaction": true,
#             "is_this_condition_hard_or_tricky_to_confidently_ascertain": false,
#             "rationale": "The client asked for a science fiction movie recommendation and the assistant provided one, making this condition highly relevant.",
#             "applies_score": 9
#         }},
#         {{
#             "condition_number": "2",
#             "condition": "the client asks about movie genres",
#             "you_the_agent_already_resolved_this_according_to_the_record_of_the_interaction": true,
#             "is_this_condition_hard_or_tricky_to_confidently_ascertain": true,
#             "rationale": "The client asked about science fiction movies, but this was already addressed by the assistant.",
#             "applies_score": 3
#         }}
#     ]
# }}
# ```

# ### Example #4:
# - Interaction Events: ###
# [{{"id": "54", "kind": "<message>", "source": "user",
# "data": {{"message": "Can I add an extra pillow to my bed order?"}}}},
# {{"id": "66", "kind": "<message>", "source": "assistant",
# "data": {{"message": "An extra pillow has been added to your order."}}}},
# {{"id": "72", "kind": "<message>", "source": "user",
# "data": {{"message": "Thanks, I'll come to pick up the order. Can you tell me the address?"}}}}]
# ###
# - Conditions: ###
# 1) the client requests a modification to their order
# 2) the client asks for the store's location
# ###
# - **Expected Result**:
# ```json
# {{
#     "checks": [
#         {{
#             "condition_number": "1",
#             "condition": "the client requests a modification to their order",
#             "you_the_agent_already_resolved_this_according_to_the_record_of_the_interaction": true,
#             "is_this_condition_hard_or_tricky_to_confidently_ascertain": true,
#             "rationale": "The client requested a modification (an extra pillow) and the assistant confirmed it, making this guideline irrelevant now as it has already been addressed.",
#             "applies_score": 3
#         }},
#         {{
#             "condition_number": "2",
#             "condition": "the client asks for the store's location",
#             "you_the_agent_already_resolved_this_according_to_the_record_of_the_interaction": false,
#             "is_this_condition_hard_or_tricky_to_confidently_ascertain": true,
#             "rationale": "The client asked for the store's location, making this guideline highly relevant.",
#             "applies_score": 10
#         }}
#     ]
# }}
# ```

# ### Example #5:
# - Interaction Events: ###
# [{{"id": "21", "kind": "<message>", "source": "user",
# "data": {{"message": "Can I add an extra charger to my laptop order?"}}}},
# {{"id": "34", "kind": "<message>", "source": "assistant",
# "data": {{"message": "An extra charger has been added to your order."}}}},
# {{"id": "53", "kind": "<message>", "source": "user",
# "data": {{"message": "Do you have any external hard drives available?"}}}}]
# ###
# - Conditions: ###
# 1) the order does not exceed the limit of products
# 2) the client asks about product availability
# ###
# - **Expected Result**:
# ```json
# {{
#     "checks": [
#         {{
#             "condition_number": "1",
#             "condition": "the order does not exceed the limit of products",
#             "you_the_agent_already_resolved_this_according_to_the_record_of_the_interaction": false,
#             "rationale": "The client added an extra charger, and the order did not exceed the limit of products, making this guideline relevant.",
#             "applies_score": 9
#         }},
#         {{
#             "condition_number": "2",
#             "condition": "the client asks about product availability",
#             "you_the_agent_already_resolved_this_according_to_the_record_of_the_interaction": false,
#             "rationale": "The client asked about the availability of external hard drives, making this guideline highly relevant as it informs the user if they reach the product limit before adding another item to the cart.",
#             "applies_score": 10
#         }}
#     ]
# }}
# ```

# ### Example #6:
# - Interaction Events: ###
# [{{"id": "54", "kind": "<message>", "source": "user",
# "data": {{"message": "I disagree with you about this point."}}}},
# {{"id": "66", "kind": "<message>", "source": "assistant",
# "data": {{"message": "But I fully disproved your thesis!"}}}},
# {{"id": "72", "kind": "<message>", "source": "user",
# "data": {{"message": "Okay, fine."}}}}]
# ###
# - Conditions: ###
# 1) the user is currently eating lunch
# 2) the user agrees with you in the scope of an argument
# ###
# - **Expected Result**:
# ```json
# {{
#     "checks": [
#         {{
#             "condition_number": "1",
#             "condition": "the user is currently eating lunch",
#             "you_the_agent_already_resolved_this_according_to_the_record_of_the_interaction": false,
#             "is_this_condition_hard_or_tricky_to_confidently_ascertain": false,
#             "rationale": "There's nothing to indicate that the user is eating, lunch or otherwise",
#             "applies_score": 1
#         }},
#         {{
#             "condition_number": "2",
#             "condition": "the user agrees with you in the scope of an argument",
#             "you_the_agent_already_resolved_this_according_to_the_record_of_the_interaction": true,
#             "is_this_condition_hard_or_tricky_to_confidently_ascertain": false,
#             "rationale": "The user said 'Okay, fine', but it's possible that they are still in disagreement internally",
#             "applies_score": 4
#         }}
#     ]
# }}
# ```
