from lagom import Container
from pytest import fixture

from parlant.core.agents import AgentId
from parlant.core.customers import CustomerId
from parlant.core.sessions import SessionId

from tests.test_utilities import create_agent, create_customer, create_session


@fixture
async def agent_id(container: Container) -> AgentId:
    agent = await create_agent(container, name="test-agent")
    return agent.id


@fixture
async def customer_id(container: Container) -> CustomerId:
    customer = await create_customer(container, "Test Customer")
    return customer.id


@fixture
async def session_id(container: Container, agent_id: AgentId) -> SessionId:
    session = await create_session(container, agent_id=agent_id)
    return session.id
