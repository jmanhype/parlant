from lagom import Container
from pytest import fixture

from emcie.server.core.agents import AgentId
from emcie.server.core.sessions import SessionId

from tests.api.utils import create_agent, create_session


@fixture
async def agent_id(container: Container) -> AgentId:
    agent = await create_agent(container, name="test-agent")
    return agent.id


@fixture
async def session_id(container: Container, agent_id: AgentId) -> SessionId:
    session = await create_session(container, agent_id=agent_id)
    return session.id
