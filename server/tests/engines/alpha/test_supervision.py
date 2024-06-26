from dataclasses import dataclass
from typing import Literal
from lagom import Container
from pytest import fixture
from pytest_bdd import scenarios, given, when, then, parsers
from emcie.server.core.agents import AgentId
from emcie.server.core.end_users import EndUserId
from emcie.server.core.guidelines import Guideline, GuidelineStore
from emcie.server.core.sessions import Event, SessionId, SessionStore
from emcie.server.engines.alpha.event_producer import MessageEventProducer
from emcie.server.engines.alpha.guideline_filter import RetrievedGuideline
from emcie.server.engines.common import ProducedEvent
from tests.test_utilities import SyncAwaiter, nlp_test

roles = Literal["client", "server"]

scenarios(
    "engines/alpha/supervision.feature",
)


@dataclass
class _TestContext:
    sync_await: SyncAwaiter
    container: Container
    agent_id: AgentId
    guidelines: dict[str, Guideline]
    retrieved_guidelines: dict[str, RetrievedGuideline]
    intercations_history: list[Event]


@fixture
def context(
    sync_await: SyncAwaiter,
    container: Container,
    agent_id: AgentId,
) -> _TestContext:
    return _TestContext(
        sync_await,
        container,
        agent_id,
        guidelines=dict(),
        retrieved_guidelines=dict(),
        intercations_history=list(),
    )


@given("an empty session", target_fixture="session_id")
def given_an_empty_session(
    context: _TestContext,
) -> SessionId:
    store = context.container[SessionStore]
    session = context.sync_await(
        store.create_session(
            end_user_id=EndUserId("test_user"),
            client_id="my_client",
        )
    )
    return session.id


@given(parsers.parse('a user message, "{user_message}"'), target_fixture="session_id")
def given_a_user_message(
    context: _TestContext,
    session_id: SessionId,
    user_message: str,
) -> SessionId:
    store = context.container[SessionStore]
    session = context.sync_await(store.read_session(session_id=session_id))

    context.intercations_history.append(
        context.sync_await(
            store.create_event(
                session_id=session.id,
                source="client",
                type=Event.MESSAGE_TYPE,
                data={"message": user_message},
            )
        )
    )

    return session.id


@given(parsers.parse("a guideline {guideline_name}, to {do_something} when {a_condition_holds}"))
def given_a_guideline_to_when(
    context: _TestContext,
    guideline_name: str,
    do_something: str,
    a_condition_holds: str,
) -> None:
    guideline_store = context.container[GuidelineStore]
    context.guidelines[guideline_name] = context.sync_await(
        guideline_store.create_guideline(
            guideline_set=context.agent_id,
            predicate=a_condition_holds,
            content=do_something,
        )
    )


@given(
    parsers.parse(
        "retrieve the {guideline_name} guideline with a score of {score} because {rationale}"
    )
)
def given_a_retrieved_guideline(
    context: _TestContext,
    guideline_name: str,
    score: int,
    rationale: str,
) -> None:
    guideline = context.guidelines[guideline_name]
    context.retrieved_guidelines[guideline_name] = RetrievedGuideline(
        guideline=guideline,
        score=score,
        rationale=rationale,
    )


@when("message processing is triggered", target_fixture="produced_events")
def when_processing_is_triggered(
    context: _TestContext,
) -> list[ProducedEvent]:
    message_event_producer = MessageEventProducer()

    message_events = context.sync_await(
        message_event_producer.produce_events(
            context_variables=[],
            interaction_history=context.intercations_history,
            ordinary_retrieved_guidelines=context.retrieved_guidelines.values(),
            tool_enabled_guidelines={},
            staged_events=[],
        )
    )

    return list(message_events)


@then(parsers.parse("the message should contains {something}"))
def then_the_message_contains(
    produced_events: list[ProducedEvent],
    something: str,
) -> None:
    message = produced_events[-1].data["message"]

    assert nlp_test(
        context=message,
        predicate=f"the text contains {something}",
    )
