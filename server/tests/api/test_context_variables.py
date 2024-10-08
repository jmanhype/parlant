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
        client.delete(f"/agents/{agent_id}/variables/{variable_to_delete.id}")
        .raise_for_status()
        .json()
    )

    assert respone["variable_id"] == variable_to_delete.id

    response = client.get(f"/agents/{agent_id}/variables/{variable_to_delete.id}")
    assert response.status_code == status.HTTP_404_NOT_FOUND


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


async def test_that_context_variable_value_can_be_set(
    client: TestClient,
    agent_id: AgentId,
    tool_id: ToolId,
) -> None:
    variable = (
        client.post(
            f"/agents/{agent_id}/variables",
            json={
                "name": "test_variable",
                "description": "test of context variable",
                "tool_id": f"local__{tool_id}",
                "freshness_rules": None,
            },
        )
        .raise_for_status()
        .json()["variable"]
    )
    variable_id = variable["id"]

    key = "yam_choock"
    data = {"zen_level": 5000}

    value = (
        client.put(
            f"/agents/{agent_id}/variables/{variable_id}/{key}",
            json={"data": data},
        )
        .raise_for_status()
        .json()["variable_value"]
    )

    assert value["variable_id"] == variable_id
    assert value["data"] == data

    data = {"zen_level": 9000}
    value = (
        client.put(
            f"/agents/{agent_id}/variables/{variable_id}/{key}",
            json={"data": data},
        )
        .raise_for_status()
        .json()["variable_value"]
    )

    assert value["variable_id"] == variable_id
    assert value["data"] == data


async def test_that_context_variable_value_can_be_deleted(
    client: TestClient,
    agent_id: AgentId,
    tool_id: ToolId,
) -> None:
    response = client.post(
        f"/agents/{agent_id}/variables",
        json={
            "name": "test_variable",
            "description": "test of context variable",
            "tool_id": f"local__{tool_id}",
            "freshness_rules": None,
        },
    )
    assert response.status_code == status.HTTP_201_CREATED
    variable = response.json()["variable"]
    variable_id = variable["id"]

    key = "yam_choock"
    data = {"zen_level": 9000}

    response = client.put(
        f"/agents/{agent_id}/variables/{variable_id}/{key}",
        json={"data": data},
    )

    variable_value = response.json()["variable_value"]
    assert variable_value["variable_id"] == variable_id
    assert variable_value["data"] == data
    assert "last_modified" in variable_value

    response = client.delete(f"/agents/{agent_id}/variables/{variable_id}/{key}")
    deleted_value_id = response.json()["variable_value_id"]
    assert deleted_value_id == variable_value["id"]

    response = client.get(f"/agents/{agent_id}/variables/{variable_id}/{key}")
    assert response.status_code == status.HTTP_404_NOT_FOUND
