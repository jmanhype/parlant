from dataclasses import dataclass
from typing import Iterable, Literal, cast
from lagom import Container
from pytest import fixture, mark
from emcie.server.core.agents import AgentId
from emcie.server.core.end_users import EndUserId
from emcie.server.core.guidelines import Guideline, GuidelineStore
from emcie.server.core.sessions import Event, SessionId, SessionStore
from emcie.server.engines.alpha.guideline_filter import GuidelineFilter
from tests.test_utilities import SyncAwaiter

roles = Literal["client", "server"]


@dataclass
class TestContext:
    sync_await: SyncAwaiter
    container: Container
    agent_id: AgentId


@fixture
def context(sync_await: SyncAwaiter, container: Container, agent_id: AgentId) -> TestContext:
    return TestContext(sync_await, container, agent_id)


@fixture
def session_id(context: TestContext) -> SessionId:
    session_store = context.container[SessionStore]
    session = context.sync_await(
        session_store.create_session(
            end_user_id=EndUserId("test_user"),
            client_id="my_client",
        )
    )
    return session.id


def create_event_message(
    context: TestContext, session_id: SessionId, role: roles, message: str
) -> Event:
    store = context.container[SessionStore]
    session = context.sync_await(store.read_session(session_id=session_id))

    event = context.sync_await(
        store.create_event(
            session_id=session.id,
            source=role,
            type=Event.MESSAGE_TYPE,
            data={"message": message},
        )
    )
    return event


def create_guideline_by_name(context: TestContext, guideline_name: str) -> Guideline:
    guideline_store = context.container[GuidelineStore]

    def create_guideline(predicate: str, content: str) -> Guideline:
        return context.sync_await(
            guideline_store.create_guideline(
                guideline_set=context.agent_id,
                predicate=predicate,
                content=content,
            )
        )

    guidelines = {
        "check_drinks_in_stock": {
            "predicate": "a client asks for a drink",
            "content": "check if the drink is available in the following stock: "
            "['Sprite', 'Coke', 'Fanta']",
        },
        "check_toppings_in_stock": {
            "predicate": "a client asks for toppings",
            "content": "check if the toppings are available in the following stock: "
            "['Pepperoni', 'Tomatoes', 'Olives']",
        },
        "payment_process": {
            "predicate": "a client is in the payment process",
            "content": "Follow the payment instructions, "
            "which are: 1. Pay in cash only, 2. Pay only at the location.",
        },
        "address_location": {
            "predicate": "the client needs to know our address",
            "content": "Inform the client that our address is at Sapir 2, Herzliya.",
        },
        "mood_support": {
            "predicate": "the client expresses stress or dissatisfaction",
            "content": "Provide comforting responses and suggest alternatives "
            "or support to alleviate the client's mood.",
        },
        "class_booking": {
            "predicate": "the client asks about booking a class or an appointment",
            "content": "Provide available times and facilitate the booking process, "
            "ensuring to clarify any necessary details such as class type, date, and requirements.",
        },
    }

    return create_guideline(**guidelines[guideline_name])


@mark.parametrize(
    "conversation_context, conversation_guideline_names, relevant_guideline_names",
    [
        (
            [
                ("client", "I'd like to order a pizza, please."),
                ("server", "No problem. What would you like to have?"),
                ("client", "I'd like a large pizza. What toppings do you have?"),
                ("server", "Today, we have pepperoni, tomatoes, and olives available."),
                ("client", "I'll take pepperoni, thanks."),
                (
                    "server",
                    "Awesome. I've added a large pepperoni pizza. "
                    "Would you like a drink on the side?",
                ),
                ("client", "Sure. What types of drinks do you have?"),
                ("server", "We have Sprite, Coke, and Fanta."),
                ("client", "I'll take two Sprites, please."),
                ("server", "Anything else?"),
                ("client", "No, that's all. I want to pay."),
                ("server", "No problem! We accept only cash."),
                ("client", "Sure, I'll pay the delivery guy."),
                ("server", "Unfortunately, we accept payments only at our location."),
                ("client", "So what should I do now?"),
            ],
            [
                "check_toppings_in_stock",
                "check_drinks_in_stock",
                "payment_process",
                "address_location",
            ],
            [
                "payment_process",
            ],
        ),
        (
            [
                (
                    "client",
                    "I'm feeling a bit stressed about coming in. Can I cancel my class for today?",
                ),
                (
                    "server",
                    "I'm sorry to hear that. While cancellation is not possible now, "
                    "how about a lighter session? Maybe it helps to relax.",
                ),
                ("client", "I suppose that could work. What do you suggest?"),
                (
                    "server",
                    "How about our guided meditation session? "
                    "It’s very calming and might be just what you need right now.",
                ),
                ("client", "Alright, please book me into that. Thank you for understanding."),
                (
                    "server",
                    "You're welcome! I've switched your booking to the meditation session. "
                    "Remember, it's okay to feel stressed. We're here to support you.",
                ),
                ("client", "Thanks, I really appreciate it."),
                ("server", "Anytime! Is there anything else I can assist you with today?"),
                ("client", "No, that's all for now."),
                (
                    "server",
                    "Take care and see you soon at the meditation class. "
                    "Our gym is at Sapir 2, Herzliya, in case you need directions.",
                ),
            ],
            [
                "class_booking",
                "mood_support",
                "address_location",
            ],
            [
                "mood_support",
            ],
        ),
    ],
)
def test_that_relevant_guidelines_are_retrieved(
    context: TestContext,
    session_id: SessionId,
    conversation_context: list[tuple[str, str]],
    conversation_guideline_names: list[str],
    relevant_guideline_names: list[str],
) -> None:
    conversation_guidelines = {
        g_name: create_guideline_by_name(context, g_name) for g_name in conversation_guideline_names
    }
    relevant_guidelines = [
        conversation_guidelines[g_name]
        for g_name in conversation_guidelines
        if g_name in relevant_guideline_names
    ]

    retrieved_guidelines = retrieve_guidelines(context, session_id, conversation_context)

    for guideline in relevant_guidelines:
        assert guideline in retrieved_guidelines


@mark.parametrize(
    "conversation_context, conversation_guideline_names, irrelevant_guideline_names",
    [
        (
            [
                ("client", "I'd like to order a pizza, please."),
                ("server", "No problem. What would you like to have?"),
                ("client", "I'd like a large pizza. What toppings do you have?"),
                ("server", "Today we have pepperoni, tomatoes, and olives available."),
                ("client", "I'll take pepperoni, thanks."),
                (
                    "server",
                    "Awesome. I've added a large pepperoni pizza. "
                    "Would you like a drink on the side?",
                ),
                ("client", "Sure. What types of drinks do you have?"),
                ("server", "We have Sprite, Coke, and Fanta."),
                ("client", "I'll take two Sprites, please."),
                ("server", "Anything else?"),
                ("client", "No, that's all."),
                ("server", "How would you like to pay?"),
                ("client", "I'll pick it up and pay in cash, thanks."),
            ],
            ["check_toppings_in_stock", "check_drinks_in_stock"],
            ["check_toppings_in_stock", "check_drinks_in_stock"],
        ),
        (
            [
                ("client", "Could you add some pretzels to my order?"),
                ("server", "Pretzels have been added to your order. Anything else?"),
                ("client", "Do you have Coke? I'd like one, please."),
                ("server", "Coke has been added to your order."),
                ("client", "Great, where are you located at?"),
            ],
            ["check_drinks_in_stock"],
            ["check_drinks_in_stock"],
        ),
    ],
)
def test_that_irrelevant_guidelines_are_not_retrieved(
    context: TestContext,
    session_id: SessionId,
    conversation_context: list[tuple[str, str]],
    conversation_guideline_names: list[str],
    irrelevant_guideline_names: list[str],
) -> None:
    conversation_guidelines = {
        g_name: create_guideline_by_name(context, g_name) for g_name in conversation_guideline_names
    }

    irrelevant_guidelines = [
        conversation_guidelines[g_name]
        for g_name in conversation_guidelines
        if g_name in irrelevant_guideline_names
    ]

    retrieved_guidelines = retrieve_guidelines(context, session_id, conversation_context)

    for guideline in retrieved_guidelines:
        assert guideline not in irrelevant_guidelines


def retrieve_guidelines(
    context: TestContext,
    session_id: SessionId,
    conversation_context: list[tuple[str, str]],
) -> Iterable[Guideline]:
    guideline_store = context.container[GuidelineStore]
    guide_filter = GuidelineFilter()

    interaction_history = [
        create_event_message(context, session_id, cast(roles, r), m)
        for r, m in conversation_context
    ]

    all_possible_guidelines = context.sync_await(
        guideline_store.list_guidelines(guideline_set=context.agent_id)
    )

    retrieved_guidelines = context.sync_await(
        guide_filter.find_relevant_guidelines(
            guidelines=all_possible_guidelines,
            context_variables=[],
            interaction_history=interaction_history,
        )
    )

    return retrieved_guidelines
