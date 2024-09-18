from datetime import datetime, timezone
from lagom import Container
from pytest import fixture

from emcie.server.core.agents import Agent, AgentId, AgentStore

from emcie.server.core.end_users import EndUserId
from emcie.server.core.sessions import Session, SessionStore
from tests.core.engines.alpha.utils import ContextOfTest
from tests.test_utilities import SyncAwaiter


@fixture
def context(sync_await: SyncAwaiter, container: Container) -> ContextOfTest:
    return ContextOfTest(
        sync_await,
        container,
        events=list(),
        guidelines=dict(),
        guideline_propositions=dict(),
        tools=dict(),
    )


@fixture
def agent(context: ContextOfTest) -> Agent:
    store = context.container[AgentStore]
    agent = context.sync_await(store.create_agent(name="test-agent"))
    return agent


@fixture
def agent_id(agent: Agent) -> AgentId:
    return agent.id


@fixture
def new_session(
    context: ContextOfTest,
    agent_id: AgentId,
) -> Session:
    store = context.container[SessionStore]
    utc_now = datetime.now(timezone.utc)
    return context.sync_await(
        store.create_session(
            creation_utc=utc_now,
            end_user_id=EndUserId("test_user"),
            agent_id=agent_id,
        )
    )
