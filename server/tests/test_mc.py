from dataclasses import dataclass
from lagom import Container
from pytest import fixture

from emcie.server.core.agents import AgentId, AgentStore
from emcie.server.core.end_users import EndUserId, EndUserStore
from emcie.server.core.guidelines import GuidelineStore
from emcie.server.core.sessions import SessionStore
from emcie.server.mc import MC


@dataclass
class _TestContext:
    container: Container
    mc: MC
    end_user_id: EndUserId


@fixture
async def context(
    container: Container,
    mc: MC,
    end_user_id: EndUserId,
) -> _TestContext:
    return _TestContext(
        container=container,
        mc=mc,
        end_user_id=end_user_id,
    )


@fixture
async def mc(container: Container) -> MC:
    return MC(container)


@fixture
async def agent_id(container: Container) -> AgentId:
    store = container[AgentStore]
    agent = await store.create_agent()
    return agent.id


@fixture
async def proactive_agent_id(container: Container, agent_id: AgentId) -> AgentId:
    await container[GuidelineStore].create_guideline(
        guideline_set=agent_id,
        predicate="The user hasn't engaged yet",
        content="Greet the user",
    )

    return agent_id


@fixture
async def end_user_id(container: Container) -> EndUserId:
    store = container[EndUserStore]
    user = await store.create_end_user("Larry David", email="larry@seinfeld.com")
    return user.id


async def test_that_a_new_end_user_session_can_be_created(
    context: _TestContext,
    agent_id: AgentId,
) -> None:
    created_session = await context.mc.create_end_user_session(
        end_user_id=context.end_user_id,
        agent_id=agent_id,
    )

    session_in_db = await context.container[SessionStore].read_session(
        created_session.id,
    )

    assert created_session == session_in_db


async def test_that_a_new_user_session_with_a_proactive_agent_contains_a_message(
    context: _TestContext,
    proactive_agent_id: AgentId,
) -> None:
    session = await context.mc.create_end_user_session(
        end_user_id=context.end_user_id,
        agent_id=proactive_agent_id,
    )

    events = list(await context.container[SessionStore].list_events(session.id))

    assert len(events) == 1
