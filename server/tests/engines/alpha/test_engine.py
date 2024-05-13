from typing import Callable, List
from lagom import Container
from pytest_bdd import scenarios, given, when, then, parsers

from emcie.server.agents import AgentId, AgentStore
from emcie.server.engines.alpha.engine import AlphaEngine
from emcie.server.engines.common import Context, ProducedEvent
from emcie.server.guidelines import Guideline, GuidelineStore
from emcie.server.sessions import Event, SessionId, SessionStore

from tests.test_utilities import SyncAwaiter, nlp_test

scenarios(
    "engines/alpha/vanilla_agent.feature",
    "engines/alpha/message_agent_with_rules.feature",
)


@given("the alpha engine", target_fixture="engine")
def given_the_alpha_engine(
    container: Container,
) -> AlphaEngine:
    return AlphaEngine(
        session_store=container[SessionStore],
        guideline_store=container[GuidelineStore],
    )


@given("an agent", target_fixture="agent_id")
def given_an_agent(
    sync_await: SyncAwaiter,
    container: Container,
) -> AgentId:
    store = container[AgentStore]
    agent = sync_await(store.create_agent())
    return agent.id


@given(parsers.parse("a guideline to {do_something}"))
def given_a_guideline_to(
    do_something: str,
    sync_await: SyncAwaiter,
    container: Container,
    agent_id: AgentId,
) -> Guideline:
    guideline_store = container[GuidelineStore]

    guidelines: dict[str, Callable[[], Guideline]] = {
        "greet with 'Howdy'": lambda: sync_await(
            guideline_store.create_guideline(
                guideline_set=agent_id,
                predicate="It's time to greet the user",
                content="Use the word 'Howdy'",
            )
        ),
        "offer thirsty users a Pepsi": lambda: sync_await(
            guideline_store.create_guideline(
                guideline_set=agent_id,
                predicate="The user is thirsty",
                content="Offer the user a Pepsi",
            )
        ),
    }

    return guidelines[do_something]()


@given("an empty session", target_fixture="session_id")
def given_an_empty_session(
    sync_await: SyncAwaiter,
    container: Container,
) -> SessionId:
    store = container[SessionStore]
    session = sync_await(store.create_session(client_id="my_client"))
    return session.id


@given("a session with a single user message", target_fixture="session_id")
def given_a_session_with_a_single_user_message(
    sync_await: SyncAwaiter,
    container: Container,
) -> SessionId:
    store = container[SessionStore]
    session = sync_await(store.create_session(client_id="my_client"))

    sync_await(
        store.create_event(
            session_id=session.id,
            source="client",
            type=Event.MESSAGE_TYPE,
            data={"message": "Hey there"},
        )
    )

    return session.id


@given("a session with a thirsty user", target_fixture="session_id")
def given_a_session_with_a_thirsty_user(
    sync_await: SyncAwaiter,
    container: Container,
) -> SessionId:
    store = container[SessionStore]
    session = sync_await(store.create_session(client_id="my_client"))

    sync_await(
        store.create_event(
            session_id=session.id,
            source="client",
            type=Event.MESSAGE_TYPE,
            data={"message": "I'm thirsty"},
        )
    )

    return session.id


@given("a session with a few messages", target_fixture="session_id")
def given_a_session_with_a_few_messages(
    sync_await: SyncAwaiter,
    container: Container,
) -> SessionId:
    store = container[SessionStore]
    session = sync_await(store.create_session(client_id="my_client"))

    messages = [
        {
            "source": "client",
            "message": "hey there",
        },
        {
            "source": "server",
            "message": "Hi, how can I help you today?",
        },
        {
            "source": "client",
            "message": "What was the first name of the famous Einstein?",
        },
    ]

    for m in messages:
        sync_await(
            store.create_event(
                session_id=session.id,
                source=m["source"] == "server" and "server" or "client",
                type=Event.MESSAGE_TYPE,
                data={"message": m["message"]},
            )
        )

    return session.id


@when("processing is triggered", target_fixture="produced_events")
def when_processing_is_triggered(
    sync_await: SyncAwaiter,
    engine: AlphaEngine,
    agent_id: AgentId,
    session_id: SessionId,
) -> List[ProducedEvent]:
    events = sync_await(
        engine.process(
            Context(
                session_id=session_id,
                agent_id=agent_id,
            )
        )
    )

    return list(events)


@then("no events are produced")
def then_no_events_are_produced(
    produced_events: List[ProducedEvent],
) -> None:
    assert len(produced_events) == 0


@then("a single message event is produced")
def then_a_single_message_event_is_produced(
    produced_events: List[ProducedEvent],
) -> None:
    assert len(produced_events) == 1


@then(parsers.parse("the message contains {something}"))
def then_the_message_contains(
    produced_events: List[ProducedEvent],
    something: str,
) -> None:
    message = produced_events[0].data["message"]

    assert nlp_test(
        context=message,
        predicate=f"the text contains {something}",
    )
