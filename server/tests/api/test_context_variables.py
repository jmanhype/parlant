from fastapi import status
from fastapi.testclient import TestClient
from lagom import Container
from pytest import fixture

from emcie.common.tools import ToolId
from emcie.server.core.agents import AgentId
from emcie.server.core.context_variables import ContextVariableStore
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


async def test_that_context_variable_can_be_removed(
    client: TestClient,
    container: Container,
    agent_id: AgentId,
    tool_id: ToolId,
) -> None:
    context_variable_store = container[ContextVariableStore]

    variable_to_delete = await context_variable_store.create_variable(
        variable_set=agent_id,
        name="test_variable",
        description="test variable",
        tool_id=tool_id,
        freshness_rules=None,
    )

    respone = (
        client.delete(f"/agents/{agent_id}/variables/{variable_to_delete.id}/")
        .raise_for_status()
        .json()
    )

    assert respone["variable_id"] == variable_to_delete.id


async def test_that_context_variables_can_be_listed(
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

    first_variable = (
        client.post(
            f"/agents/{agent_id}/variables",
            json={
                "name": "test_variable",
                "description": "test of context variable",
                "tool_id": f"local__{tool_id}",
                "freshness_rules": freshness_rules,
            },
        )
        .raise_for_status()
        .json()["variable"]
    )

    second_variable = (
        client.post(
            f"/agents/{agent_id}/variables",
            json={
                "name": "second_test_variable",
                "tool_id": f"local__{tool_id}",
            },
        )
        .raise_for_status()
        .json()["variable"]
    )

    variables = client.get(f"/agents/{agent_id}/variables/").raise_for_status().json()["variables"]
    assert len(variables) == 2

    assert any(first_variable == v for v in variables)
    assert any(second_variable == v for v in variables)
