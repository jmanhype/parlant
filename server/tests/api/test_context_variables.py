from fastapi import status
from fastapi.testclient import TestClient
from lagom import Container
from pytest import fixture

from emcie.common.tools import ToolId
from emcie.server.core.agents import AgentId
from emcie.server.core.tools import LocalToolService


@fixture
async def tool_id(
    container: Container,
) -> ToolId:
    tool_store = container[LocalToolService]

    return (
        await tool_store.create_tool(
            name="get_terrys_offering",
            module_path="tests.tool_utilities",
            description="Explain Terry's offering",
            parameters={},
            required=[],
        )
    ).id


async def test_that_context_variable_can_be_created(
    client: TestClient,
    agent_id: AgentId,
    tool_id: ToolId,
) -> None:
    freshness_rules = {
        "months": [5],
        "days_of_month": [14],
        "days_of_week": ["Thursday"],
        "hours": [18],
        "minutes": None,
        "seconds": None,
    }

    response = client.post(
        f"/agents/{agent_id}/variables",
        json={
            "name": "test_variable",
            "description": "test of context variable",
            "tool_id": f"local__{tool_id}",
            "freshness_rules": freshness_rules,
        },
    )

    assert response.status_code == status.HTTP_201_CREATED

    context_variable = response.json()["variable"]
    assert context_variable["name"] == "test_variable"
    assert context_variable["description"] == "test of context variable"
    assert context_variable["freshness_rules"] == freshness_rules
