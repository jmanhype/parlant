import asyncio
from typing import Any, Awaitable, Generator, List, TypeVar
from lagom import Container
from pytest import fixture
from pytest_bdd import scenarios, given, when, then

from emcie.server.agents import AgentId, AgentStore
from emcie.server.engines.alpha.engine import AlphaEngine
from emcie.server.engines.common import Context
from emcie.server.sessions import Event, SessionId, SessionStore


scenarios("engines/alpha/vanilla_configuration.feature")

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
    return AlphaEngine()


@given("an agent", target_fixture="agent_id")
def given_an_agent(
    container: Container,
    sync_await: SyncAwaiter,
) -> AgentId:
    store = container[AgentStore]
    agent = sync_await(store.create_agent())
    return agent.id


@given("an empty session", target_fixture="session_id")
def given_an_empty_session(
    container: Container,
    sync_await: SyncAwaiter,
) -> SessionId:
    store = container[SessionStore]
    session = sync_await(store.create_session("my_client"))
    return session.id


@when("processing is triggered", target_fixture="generated_events")
def when_processing_is_triggered(
    sync_await: SyncAwaiter,
    engine: AlphaEngine,
    agent_id: AgentId,
    session_id: SessionId,
) -> List[Event]:
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
    generated_events: List[Event],
) -> None:
    assert len(generated_events) == 0
