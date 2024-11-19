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
from parlant.core.context_variables import ContextVariable, ContextVariableValue
from parlant.core.emissions import EmittedEvent
from parlant.core.glossary import Term
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
from parlant.core.glossary import TermId

from tests.core.engines.alpha.utils import create_event_message
from tests.test_utilities import SyncAwaiter


GUIDELINES_DICT = {
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
    "class_cancellation": {
        "condition": "the client wants to cancel a class or an appointment",
        "action": "ask for the reason of cancellation, unless it's an emergecy mention the cancellation fee.",
    },
    "frustrated_user": {
        "condition": "the client appears frustrated or upset",
        "action": "Acknowledge the client's concerns, apologize for any inconvenience, and offer a solution or escalate the issue to a supervisor if necessary.",
    },
    "thankful_user": {
        "condition": "the client expresses gratitude or satisfaction",
        "action": "Acknowledge their thanks warmly and let them know you appreciate their feedback or kind words.",
    },
    "hesitant_user": {
        "condition": "the client seems unsure or indecisive about a decision",
        "action": "Offer additional information, provide reassurance, and suggest the most suitable option based on their needs.",
    },
    "holiday_season": {
        "condition": "the interaction takes place during the holiday season",
        "action": "Mention any holiday-related offers, adjusted schedules, or greetings to make the interaction festive and accommodating.",
    },
    "previous_issue_resurfaced": {
        "condition": "the client brings up an issue they previously experienced",
        "action": "Acknowledge the previous issue, apologize for any inconvenience, and take immediate steps to resolve it or escalate if needed.",
    },
    "question_already_answered": {
        "condition": "the client asks a question that has already been answered",
        "action": "Politely reiterate the information and ensure they understand or provide additional clarification if needed.",
    },
    "product_out_of_stock": {
        "condition": "the client asks for a product that is currently unavailable",
        "action": "Apologize for the inconvenience, inform them of the unavailability, and suggest alternative products or notify them of restocking timelines if available.",
    },
    "technical_issue": {
        "condition": "the client reports a technical issue with the website or service",
        "action": "Acknowledge the issue, apologize for the inconvenience, and guide them through troubleshooting steps or escalate the issue to the technical team.",
    },
    "first_time_client": {
        "condition": "the client mentions it is their first time using the service",
        "action": "Welcome them warmly, provide a brief overview of how the service works, and offer any resources to help them get started.",
    },
    "request_for_feedback": {
        "condition": "the client is asked for feedback about the service or product",
        "action": "Politely request their feedback, emphasizing its value for improvement, and provide simple instructions for submitting their response.",
    },
    "client_refers_friends": {
        "condition": "the client mentions referring friends to the service or product",
        "action": "Thank them sincerely for the referral and mention any referral rewards or benefits if applicable.",
    },
    "check_age": {
        "condition": "the conversation neccesitates checking for the age of the client",
        "action": "Use the 'check_age' tool to check for their age",
    },
    "suggest_drink_underage": {
        "condition": "an underage client asks for drink recommendations",
        "action": "recommend a soda pop",
    },
    "suggest_drink_adult": {
        "condition": "an adult client asks for drink recommendations",
        "action": "recommend either wine or beer",
    },
    "announce_shipment": {
        "condition": "the agent just confirmed that the order will be shipped to the user",
        "action": "provide the package's tracking information",
    },
    "tree_allergies": {
        "condition": "recommending routes to a user with tree allergies",
        "action": "warn the user about allergy inducing trees along the route",
    },
    "credit_payment1": {
        "condition": "the user requests a credit card payment",
        "action": "guide the user through the payment process",
    },
    "credit_payment2": {
        "condition": "the user wants to pay with a credit card",
        "action": "refuse payment as we only perform in-store purchases",
    },
    "cant_perform_request": {
        "condition": "the user wants to agent to perform an action that the agent is not designed for",
        "action": "forward the request to a supervisor",
    },
}


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
    context_variables: Sequence[tuple[ContextVariable, ContextVariableValue]] = [],
    terms: Sequence[Term] = [],
    staged_events: Sequence[EmittedEvent] = [],
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
            context_variables=context_variables,
            interaction_history=interaction_history,
            terms=terms,
            staged_events=staged_events,
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


def create_term(name: str, description: str, synonyms: list[str] = []) -> Guideline:
    return Term(
        id=TermId("-"),
        creation_utc=datetime.now(timezone.utc),
        name=name,
        description=description,
        synonyms=synonyms,
    )


def get_all_guidelines(context: ContextOfTest) -> Sequence[Guideline]:
    return [
        create_guideline(
            context=context, condition=guideline["condition"], action=guideline["action"]
        )
        for guideline in GUIDELINES_DICT.values()
    ]


def create_guideline_by_name(
    context: ContextOfTest,
    guideline_name: str,
) -> Guideline:
    guideline = create_guideline(
        context=context,
        condition=GUIDELINES_DICT[guideline_name]["condition"],
        action=GUIDELINES_DICT[guideline_name]["action"],
    )
    return guideline


def base_test_that_correct_guidelines_are_proposed(
    context: ContextOfTest,
    conversation_context: list[tuple[str, str]],
    conversation_guideline_names: list[str],
    relevant_guideline_names: list[str],
    agents: Sequence[Agent] = [],
    context_variables: Sequence[tuple[ContextVariable, ContextVariableValue]] = [],
    terms: Sequence[Term] = [],
    staged_events: Sequence[EmittedEvent] = [],
) -> None:
    conversation_guidelines = {
        name: create_guideline_by_name(context, name) for name in conversation_guideline_names
    }
    relevant_guidelines = [
        conversation_guidelines[name]
        for name in conversation_guidelines
        if name in relevant_guideline_names
    ]

    guideline_propositions = propose_guidelines(
        context,
        conversation_context,
        agents=agents,
        context_variables=context_variables,
        terms=terms,
        staged_events=staged_events,
    )
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
    conversation_context: list[tuple[str, str]] = [
        ("end_user", "Hey, do you sell skateboards?"),
        (
            "ai_agent",
            "Yes, we do! We have a variety of skateboards for all skill levels. Are you looking for something specific?",
        ),
        ("end_user", "I'm looking for a skateboard for a beginner. What do you recommend?"),
        (
            "ai_agent",
            "For beginners, I recommend our complete skateboards with a sturdy deck and softer wheels for easier control. Would you like to see some options?",
        ),
        ("end_user", "That sounds perfect. Can you show me a few?"),
        (
            "ai_agent",
            "Sure! We have a few options: the 'Smooth Ride' model, the 'City Cruiser,' and the 'Basic Starter.' Which one would you like to know more about?",
        ),
        ("end_user", "I like the 'City Cruiser.' What color options do you have?"),
        ("ai_agent", "The 'City Cruiser' comes in red, blue, and black. Which one do you prefer?"),
        ("end_user", "I'll go with the blue one."),
        (
            "ai_agent",
            "Great choice! I'll add the blue 'City Cruiser' to your cart. Would you like to add any accessories like a helmet or grip tape?",
        ),
        ("end_user", "Yes, I'll take a helmet. What do you have in stock?"),
        (
            "ai_agent",
            "We have helmets in small, medium, and large sizes, all available in black and gray. What size do you need?",
        ),
        ("end_user", "I need a medium. I'll take one in black."),
        (
            "ai_agent",
            "Got it! Your blue 'City Cruiser' skateboard and black medium helmet are ready for checkout. How would you like to pay?",
        ),
        ("end_user", "I'll pay with a credit card, thanks."),
        (
            "ai_agent",
            "Thank you for your order! Your skateboard and helmet will be shipped shortly. Enjoy your ride!",
        ),
    ]

    conversation_guideline_names: list[str] = [
        guideline_name for guideline_name in GUIDELINES_DICT.keys()
    ]
    relevant_guideline_names = ["announce_shipment"]
    base_test_that_correct_guidelines_are_proposed(
        context, conversation_context, conversation_guideline_names, relevant_guideline_names
    )


def test_that_guidelines_are_proposed_based_on_agent_description(  # TODO alter
    context: ContextOfTest,
) -> None:
    agent = Agent(
        id=AgentId("123"),
        creation_utc=datetime.now(timezone.utc),
        name="skaetboard-sales-agent",
        description="You are an agent working for a skateboarding manufacturer. You help clients by discussing and recommending our products."
        "Your role is only to consult clients, and not to actually sell anything, as we sell our products in-store.",
        max_engine_iterations=3,
    )
    conversation_context: list[tuple[str, str]] = [
        ("end_user", "Hey, do you sell skateboards?"),
        (
            "ai_agent",
            "Yes, we do! We have a variety of skateboards for all skill levels. Are you looking for something specific?",
        ),
        ("end_user", "I'm looking for a skateboard for a beginner. What do you recommend?"),
        (
            "ai_agent",
            "For beginners, I recommend our complete skateboards with a sturdy deck and softer wheels for easier control. Would you like to see some options?",
        ),
        ("end_user", "That sounds perfect. Can you show me a few?"),
        (
            "ai_agent",
            "Sure! We have a few options: the 'Smooth Ride' model, the 'City Cruiser,' and the 'Basic Starter.' Which one would you like to know more about?",
        ),
        ("end_user", "I like the 'City Cruiser.' What color options do you have?"),
        ("ai_agent", "The 'City Cruiser' comes in red, blue, and black. Which one do you prefer?"),
        (
            "end_user",
            "I'll go with the blue one. My credit card number is 4242 4242 4242 4242, please charge it and ship the product to my address.",
        ),
    ]

    conversation_guideline_names: list[str] = ["cant_perform_request"]
    relevant_guideline_names = ["cant_perform_request"]
    base_test_that_correct_guidelines_are_proposed(
        context,
        conversation_context,
        conversation_guideline_names,
        relevant_guideline_names,
        agents=[agent],
    )


def test_that_guidelines_are_proposed_based_on_glossary(
    context: ContextOfTest,
) -> None:
    terms = [
        create_term(
            name="skateboard",
            description="a time-travelling device",
        ),
        create_term(
            name="Pinewood Rash Syndrome",
            description="allergy to pinewood trees",
            synonyms=["Pine Rash", "PRS"],
        ),
    ]
    conversation_context: list[tuple[str, str]] = [
        ("end_user", "Hi, I’m looking for a hiking route through a forest. Can you help me?"),
        (
            "ai_agent",
            "Of course! I can help you find a trail. Are you looking for an easy, moderate, or challenging hike?",
        ),
        ("end_user", "I’d prefer something moderate, not too easy but also not too tough."),
        (
            "ai_agent",
            "Great choice! We have a few moderate trails in the Redwood Forest and the Pinewood Trail. Would you like details on these?",
        ),
        ("end_user", "Yes, tell me more about the Pinewood Trail."),
        (
            "ai_agent",
            "The Pinewood Trail is a 6-mile loop with moderate elevation changes. It takes about 3-4 hours to complete. The scenery is beautiful, with plenty of shade and a stream crossing halfway through. Would you like to go with that one?",
        ),
        ("end_user", "I have PRS, would that route be suitable for me?"),
    ]
    conversation_guideline_names: list[str] = [
        "recommending_routes",
        "mood_support",
        "first_time_client",
    ]
    relevant_guideline_names = ["tree_allergies"]
    base_test_that_correct_guidelines_are_proposed(
        context,
        conversation_context,
        conversation_guideline_names,
        relevant_guideline_names,
        terms=terms,
    )


def test_that_conflicting_actions_with_similar_conditions_are_both_detected(
    context: ContextOfTest,
) -> None:
    conversation_context: list[tuple[str, str]] = [
        ("end_user", "Hey, do you sell skateboards?"),
        (
            "ai_agent",
            "Yes, we do! We have a variety of skateboards for all skill levels. Are you looking for something specific?",
        ),
        ("end_user", "I'm looking for a skateboard for a beginner. What do you recommend?"),
        (
            "ai_agent",
            "For beginners, I recommend our complete skateboards with a sturdy deck and softer wheels for easier control. Would you like to see some options?",
        ),
        ("end_user", "That sounds perfect. Can you show me a few?"),
        (
            "ai_agent",
            "Sure! We have a few options: the 'Smooth Ride' model, the 'City Cruiser,' and the 'Basic Starter.' Which one would you like to know more about?",
        ),
        ("end_user", "I like the 'City Cruiser.' What color options do you have?"),
        ("ai_agent", "The 'City Cruiser' comes in red, blue, and black. Which one do you prefer?"),
        ("end_user", "I'll go with the blue one."),
        (
            "ai_agent",
            "Great choice! I'll add the blue 'City Cruiser' to your cart. Would you like to add any accessories like a helmet or grip tape?",
        ),
        ("end_user", "Yes, I'll take a helmet. What do you have in stock?"),
        (
            "ai_agent",
            "We have helmets in small, medium, and large sizes, all available in black and gray. What size do you need?",
        ),
        ("end_user", "I need a medium. I'll take one in black."),
        (
            "ai_agent",
            "Got it! Your blue 'City Cruiser' skateboard and black medium helmet are ready for checkout. How would you like to pay?",
        ),
        ("end_user", "I'll pay with a credit card, thanks."),
    ]
    conversation_guideline_names: list[str] = ["credit_payment1", "credit_payment2"]
    relevant_guideline_names = conversation_guideline_names
    base_test_that_correct_guidelines_are_proposed(
        context, conversation_context, conversation_guideline_names, relevant_guideline_names
    )


def test_that_guidelines_are_proposed_based_on_staged_tool_calls(
    context: ContextOfTest,
) -> None:
    assert True  # TODO write


def test_that_already_adressed_guidelines_arent_proposed(
    context: ContextOfTest,
) -> None:
    assert True  # TODO write


def test_that_guideline_isnt_detected_based_on_its_action(
    context: ContextOfTest,
) -> None:
    assert True  # TODO write
