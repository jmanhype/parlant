from fastapi.testclient import TestClient
from pytest import fixture

from emcie.server.core.agents import AgentId


@fixture
def agent_id(client: TestClient) -> AgentId:
    response = client.post(
        "/agents",
        json={"agent_name": "test-agent"},
    )
    return AgentId(response.json()["agent_id"])
