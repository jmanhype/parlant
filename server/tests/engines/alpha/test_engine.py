import asyncio
from typing import Any, Awaitable, Generator, Iterable, List, TypeVar
from lagom import Container
from pytest import fixture
from pytest_bdd import scenarios, given, when, then

from emcie.server.agents import AgentId, AgentStore
from emcie.server.engines.alpha.engine import AlphaEngine
from emcie.server.engines.common import Context, ProducedEvent
from emcie.server.sessions import Event, SessionId, SessionStore


scenarios("engines/alpha/vanilla_agent.feature")

T = TypeVar("T")


class SyncAwaiter:
    def __init__(self, event_loop: asyncio.AbstractEventLoop) -> None:
        self.event_loop = event_loop

    def __call__(self, awaitable: Generator[Any, None, T] | Awaitable[T]) -> T:
        return self.event_loop.run_until_complete(awaitable)


@fixture
async def sync_await() -> SyncAwaiter:
    return SyncAwaiter(asyncio.get_event_loop())


@given("the alpha engine", target_fixture="engine")
def given_the_alpha_engine(
    container: Container,
) -> AlphaEngine:
    return AlphaEngine(
        session_store=container[SessionStore],
    )


@given("a vanilla agent", target_fixture="agent_id")
def given_an_agent(
    sync_await: SyncAwaiter,
    container: Container,
) -> AgentId:
    store = container[AgentStore]
    agent = sync_await(store.create_agent())
    return agent.id


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


@when("processing is triggered", target_fixture="generated_events")
def when_processing_is_triggered(
    sync_await: SyncAwaiter,
    engine: AlphaEngine,
    agent_id: AgentId,
    session_id: SessionId,
) -> Iterable[ProducedEvent]:
    events = sync_await(
        engine.process(
            Context(
                session_id=session_id,
                agent_id=agent_id,
            )
        )
    )

    return events


@then("no events are generated")
def then_no_events_are_generated(
    generated_events: List[ProducedEvent],
) -> None:
    assert len(generated_events) == 0


@then("one message event is generated")
def then_a_single_message_event_is_generated(
    generated_events: List[ProducedEvent],
) -> None:
    assert len(generated_events) == 1
