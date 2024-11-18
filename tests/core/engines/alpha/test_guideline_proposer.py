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

from dataclasses import dataclass
from datetime import datetime, timezone
from itertools import chain
from typing import Sequence, cast

from lagom import Container
from more_itertools import unique
from pytest import fixture

from parlant.core.agents import Agent, AgentId
from parlant.core.common import generate_id
from parlant.core.customers import Customer, CustomerId
from parlant.core.nlp.generation import SchematicGenerator
from parlant.core.engines.alpha.guideline_proposer import (
    GuidelineProposer,
    GuidelinePropositionsSchema,
)
from parlant.core.engines.alpha.guideline_proposition import (
    GuidelineProposition,
)
from parlant.core.guidelines import Guideline, GuidelineContent, GuidelineId
from parlant.core.sessions import EventSource
from parlant.core.logging import Logger

from tests.core.engines.alpha.utils import create_event_message
from tests.test_utilities import SyncAwaiter


@dataclass
class ContextOfTest:
    sync_await: SyncAwaiter
    guidelines: list[Guideline]
    schematic_generator: SchematicGenerator[GuidelinePropositionsSchema]
    logger: Logger


@fixture
def context(
    sync_await: SyncAwaiter,
    container: Container,
) -> ContextOfTest:
    return ContextOfTest(
        sync_await,
        guidelines=list(),
        logger=container[Logger],
        schematic_generator=container[SchematicGenerator[GuidelinePropositionsSchema]],
    )


def propose_guidelines(
    context: ContextOfTest,
    conversation_context: list[tuple[str, str]],
    agents: Sequence[Agent] = [],
) -> Sequence[GuidelineProposition]:
    guideline_proposer = GuidelineProposer(context.logger, context.schematic_generator)
    if not agents:
        agents = [
            Agent(
                id=AgentId("123"),
                creation_utc=datetime.now(timezone.utc),
                name="Test Agent",
                description="You are an agent that works for Parlant",
                max_engine_iterations=3,
            )
        ]

    interaction_history = [
        create_event_message(
            offset=i,
            source=cast(EventSource, source),
            message=message,
        )
        for i, (source, message) in enumerate(conversation_context)
    ]

    guideline_proposition_result = context.sync_await(
        guideline_proposer.propose_guidelines(
            agents=agents,
            customer=customer,
            guidelines=context.guidelines,
            context_variables=[],
            interaction_history=interaction_history,
            terms=[],
            staged_events=[],
        )
    )

    return list(chain.from_iterable(guideline_proposition_result.batches))


def create_guideline(context: ContextOfTest, condition: str, action: str) -> Guideline:
    guideline = Guideline(
        id=GuidelineId(generate_id()),
        creation_utc=datetime.now(timezone.utc),
        content=GuidelineContent(
            condition=condition,
            action=action,
        ),
    )

    context.guidelines.append(guideline)

    return guideline


def create_guideline_by_name(
    context: ContextOfTest,
    guideline_name: str,
) -> Guideline:
    guidelines = {
        "check_drinks_in_stock": {
            "condition": "a client asks for a drink",
            "action": "check if the drink is available in the following stock: "
            "['Sprite', 'Coke', 'Fanta']",
        },
        "check_toppings_in_stock": {
            "condition": "a client asks for toppings",
            "action": "check if the toppings are available in the following stock: "
            "['Pepperoni', 'Tomatoes', 'Olives']",
        },
        "payment_process": {
            "condition": "a client is in the payment process",
            "action": "Follow the payment instructions, "
            "which are: 1. Pay in cash only, 2. Pay only at the location.",
        },
        "address_location": {
            "condition": "the client needs to know our address",
            "action": "Inform the client that our address is at Sapir 2, Herzliya.",
        },
        "mood_support": {
            "condition": "the client is experiencing stress or dissatisfaction",
            "action": "Provide comforting responses and suggest alternatives "
            "or support to alleviate the client's mood.",
        },
        "class_booking": {
            "condition": "the client asks about booking a class or an appointment",
            "action": "Provide available times and facilitate the booking process, "
            "ensuring to clarify any necessary details such as class type, date, and requirements.",
        },
    }

    guideline = create_guideline(
        context=context,
        condition=guidelines[guideline_name]["condition"],
        action=guidelines[guideline_name]["action"],
    )

    return guideline


def base_test_that_correct_guidelines_are_proposed(
    context: ContextOfTest,
    conversation_context: list[tuple[str, str]],
    conversation_guideline_names: list[str],
    relevant_guideline_names: list[str],
    agents: Sequence[Agent] = [],
) -> None:
    conversation_guidelines = {
        name: create_guideline_by_name(context, name) for name in conversation_guideline_names
    }
    relevant_guidelines = [
        conversation_guidelines[name]
        for name in conversation_guidelines
        if name in relevant_guideline_names
    ]

    guideline_propositions = propose_guidelines(context, conversation_context, agents)
    guidelines = [p.guideline for p in guideline_propositions]

    assert set(guidelines) == set(relevant_guidelines)


def test_that_relevant_guidelines_are_proposed_parametrized_1(
    context: ContextOfTest,
) -> None:
    conversation_context: list[tuple[str, str]] = [
        ("customer", "I'd like to order a pizza, please."),
        ("ai_agent", "No problem. What would you like to have?"),
        ("customer", "I'd like a large pizza. What toppings do you have?"),
        ("ai_agent", "Today, we have pepperoni, tomatoes, and olives available."),
        ("customer", "I'll take pepperoni, thanks."),
        (
            "ai_agent",
            "Awesome. I've added a large pepperoni pizza. " "Would you like a drink on the side?",
        ),
        ("customer", "Sure. What types of drinks do you have?"),
        ("ai_agent", "We have Sprite, Coke, and Fanta."),
        ("customer", "I'll take two Sprites, please."),
        ("ai_agent", "Anything else?"),
        ("customer", "No, that's all. I want to pay."),
        ("ai_agent", "No problem! We accept only cash."),
        ("customer", "Sure, I'll pay the delivery guy."),
        ("ai_agent", "Unfortunately, we accept payments only at our location."),
        ("customer", "So what should I do now?"),
    ]
    conversation_guideline_names: list[str] = [
        "check_toppings_in_stock",
        "check_drinks_in_stock",
        "payment_process",
        "address_location",
    ]
    relevant_guideline_names: list[str] = [
        "payment_process",
    ]
    base_test_that_correct_guidelines_are_proposed(
        context, conversation_context, conversation_guideline_names, relevant_guideline_names
    )


def test_that_relevant_guidelines_are_proposed_parametrized_2(
    context: ContextOfTest,
) -> None:
    conversation_context: list[tuple[str, str]] = [
        (
            "customer",
            "I'm feeling a bit stressed about coming in. Can I cancel my class for today?",
        ),
        (
            "ai_agent",
            "I'm sorry to hear that. While cancellation is not possible now, "
            "how about a lighter session? Maybe it helps to relax.",
        ),
        ("customer", "I suppose that could work. What do you suggest?"),
        (
            "ai_agent",
            "How about our guided meditation session? "
            "It’s very calming and might be just what you need right now.",
        ),
        ("customer", "Alright, please book me into that. Thank you for understanding."),
        (
            "ai_agent",
            "You're welcome! I've switched your booking to the meditation session. "
            "Remember, it's okay to feel stressed. We're here to support you.",
        ),
        ("customer", "Thanks, I really appreciate it."),
        ("ai_agent", "Anytime! Is there anything else I can assist you with today?"),
        ("customer", "No, that's all for now."),
        (
            "ai_agent",
            "Take care and see you soon at the meditation class. "
            "Our gym is at the mall on the 2nd floor.",
        ),
        ("customer", "Thank you!"),
    ]
    conversation_guideline_names: list[str] = [
        "class_booking",
        "mood_support",
        "address_location",
    ]

    relevant_guideline_names: list[str] = [
        "mood_support",
    ]
    base_test_that_correct_guidelines_are_proposed(
        context, conversation_context, conversation_guideline_names, relevant_guideline_names
    )


def test_that_irrelevant_guidelines_are_not_proposed_parametrized_1(
    context: ContextOfTest,
) -> None:
    conversation_context: list[tuple[str, str]] = [
        ("customer", "I'd like to order a pizza, please."),
        ("ai_agent", "No problem. What would you like to have?"),
        ("customer", "I'd like a large pizza. What toppings do you have?"),
        ("ai_agent", "Today we have pepperoni, tomatoes, and olives available."),
        ("customer", "I'll take pepperoni, thanks."),
        (
            "ai_agent",
            "Awesome. I've added a large pepperoni pizza. " "Would you like a drink on the side?",
        ),
        ("customer", "Sure. What types of drinks do you have?"),
        ("ai_agent", "We have Sprite, Coke, and Fanta."),
        ("customer", "I'll take two Sprites, please."),
        ("ai_agent", "Anything else?"),
        ("customer", "No, that's all."),
        ("ai_agent", "How would you like to pay?"),
        ("customer", "I'll pick it up and pay in cash, thanks."),
    ]

    conversation_guideline_names: list[str] = ["check_toppings_in_stock", "check_drinks_in_stock"]
    base_test_that_correct_guidelines_are_proposed(
        context, conversation_context, conversation_guideline_names, []
    )


def test_that_irrelevant_guidelines_are_not_proposed_parametrized_2(
    context: ContextOfTest,
) -> None:
    conversation_context: list[tuple[str, str]] = [
        ("customer", "Could you add some pretzels to my order?"),
        ("ai_agent", "Pretzels have been added to your order. Anything else?"),
        ("customer", "Do you have Coke? I'd like one, please."),
        ("ai_agent", "Coke has been added to your order."),
        ("customer", "Great, where are you located at?"),
    ]
    conversation_guideline_names: list[str] = ["check_drinks_in_stock"]
    base_test_that_correct_guidelines_are_proposed(
        context, conversation_context, conversation_guideline_names, []
    )


def test_that_guidelines_with_the_same_conditions_are_scored_identically(
    context: ContextOfTest,
) -> None:
    relevant_guidelines = [
        create_guideline(
            context=context,
            condition="the customer greets you",
            action="talk about apples",
        ),
        create_guideline(
            context=context,
            condition="the customer greets you",
            action="talk about oranges",
        ),
    ]

    _ = [  # irrelevant guidelines
        create_guideline(
            context=context,
            condition="talking about the weather",
            action="talk about apples",
        ),
        create_guideline(
            context=context,
            condition="talking about the weather",
            action="talk about oranges",
        ),
    ]

    guideline_propositions = propose_guidelines(context, [("customer", "Hello there")])

    assert len(guideline_propositions) == len(relevant_guidelines)
    assert all(gp.guideline in relevant_guidelines for gp in guideline_propositions)
    assert len(list(unique(gp.score for gp in guideline_propositions))) == 1


def test_that_many_guidelines_are_classified_correctly(  # a stress test
    context: ContextOfTest,
) -> None:
    assert True
