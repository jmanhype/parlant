from fastapi import status
from fastapi.testclient import TestClient
from lagom import Container
from pytest import fixture

from emcie.common.tools import ToolId
from emcie.server.core.agents import AgentId
from emcie.server.core.context_variables import ContextVariableStore, FreshnessRules
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


async def test_that_all_context_variables_can_be_deleted(
    client: TestClient,
    container: Container,
    agent_id: AgentId,
    tool_id: ToolId,
) -> None:
    context_variable_store = container[ContextVariableStore]

    _ = await context_variable_store.create_variable(
        variable_set=agent_id,
        name="test_variable",
        description="test variable",
        tool_id=ToolId(f"local__{tool_id}"),
        freshness_rules=None,
    )

    _ = await context_variable_store.create_variable(
        variable_set=agent_id,
        name="test_variable",
        description="test variable",
        tool_id=ToolId(f"local__{tool_id}"),
        freshness_rules=None,
    )

    vars = await context_variable_store.list_variables(variable_set=agent_id)
    assert len(vars) == 2

    response = client.delete(f"/agents/{agent_id}/variables")
    assert response.status_code == status.HTTP_204_NO_CONTENT

    vars = await context_variable_store.list_variables(variable_set=agent_id)
    assert len(vars) == 0


async def test_that_context_variable_can_be_deleted(
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
    container: Container,
    agent_id: AgentId,
    tool_id: ToolId,
) -> None:
    context_variable_store = container[ContextVariableStore]

    first_variable = await context_variable_store.create_variable(
        variable_set=agent_id,
        name="test_variable",
        description="test variable",
        tool_id=tool_id,
        freshness_rules=FreshnessRules(
            months=[5],
            days_of_month=None,
            days_of_week=None,
            hours=None,
            minutes=None,
            seconds=None,
        ),
    )

    second_variable = await context_variable_store.create_variable(
        variable_set=agent_id,
        name="second_test_variable",
        description=None,
        tool_id=tool_id,
        freshness_rules=None,
    )

    variables = client.get(f"/agents/{agent_id}/variables/").raise_for_status().json()["variables"]
    assert len(variables) == 2

    assert first_variable.id == variables[0]["id"]
    assert second_variable.id == variables[1]["id"]

    assert first_variable.name == variables[0]["name"]
    assert second_variable.name == variables[1]["name"]

    assert first_variable.description == variables[0]["description"]
    assert second_variable.description == variables[1]["description"]

    assert first_variable.freshness_rules is not None
    assert first_variable.freshness_rules.months == variables[0]["freshness_rules"]["months"]

    assert second_variable.freshness_rules is None


async def test_that_context_variable_value_can_be_retrieved(
    client: TestClient,
    container: Container,
    agent_id: AgentId,
    tool_id: ToolId,
) -> None:
    context_variable_store = container[ContextVariableStore]

    variable = await context_variable_store.create_variable(
        variable_set=agent_id,
        name="test_variable",
        description="test variable",
        tool_id=tool_id,
        freshness_rules=None,
    )

    key = "test_key"
    data = {"value": 42}

    _ = await context_variable_store.update_value(
        variable_set=agent_id,
        variable_id=variable.id,
        key=key,
        data=data,
    )

    value = (
        client.get(f"/agents/{agent_id}/variables/{variable.id}/{key}").raise_for_status().json()
    )

    assert value["data"] == data


async def test_that_context_variable_value_can_be_set(
    client: TestClient,
    container: Container,
    agent_id: AgentId,
    tool_id: ToolId,
) -> None:
    context_variable_store = container[ContextVariableStore]

    variable = await context_variable_store.create_variable(
        variable_set=agent_id,
        name="test_variable",
        description="test variable",
        tool_id=tool_id,
        freshness_rules=None,
    )

    key = "yam_choock"
    data = {"zen_level": 5000}

    value = (
        client.put(
            f"/agents/{agent_id}/variables/{variable.id}/{key}",
            json={"data": data},
        )
        .raise_for_status()
        .json()["variable_value"]
    )

    assert value["data"] == data

    data = {"zen_level": 9000}
    value = (
        client.put(
            f"/agents/{agent_id}/variables/{variable.id}/{key}",
            json={"data": data},
        )
        .raise_for_status()
        .json()["variable_value"]
    )

    assert value["data"] == data


async def test_that_context_variable_values_can_be_listed(
    client: TestClient,
    container: Container,
    agent_id: AgentId,
    tool_id: ToolId,
) -> None:
    context_variable_store = container[ContextVariableStore]

    variable = await context_variable_store.create_variable(
        variable_set=agent_id,
        name="test_variable",
        description="test variable",
        tool_id=ToolId(f"local__{tool_id}"),
        freshness_rules=None,
    )

    keys_and_data = {
        "key1": {"value": 1},
        "key2": {"value": 2},
        "key3": {"value": 3},
    }

    for key, data in keys_and_data.items():
        _ = await context_variable_store.update_value(
            variable_set=agent_id,
            variable_id=variable.id,
            key=key,
            data=data,
        )

    response = client.get(f"/agents/{agent_id}/variables/{variable.id}")
    assert response.status_code == status.HTTP_200_OK

    retrieved_variable = response.json()["variable"]
    assert retrieved_variable["id"] == variable.id
    assert retrieved_variable["name"] == "test_variable"
    assert retrieved_variable["description"] == "test variable"
    assert retrieved_variable["tool_id"] == f"local__{tool_id}"

    retrieved_values = response.json()["variable_values"]

    assert len(retrieved_values) == len(keys_and_data)
    for key in keys_and_data:
        assert key in retrieved_values
        assert retrieved_values[key]["data"] == keys_and_data[key]


async def test_that_context_variable_value_can_be_deleted(
    client: TestClient,
    container: Container,
    agent_id: AgentId,
    tool_id: ToolId,
) -> None:
    context_variable_store = container[ContextVariableStore]

    variable = await context_variable_store.create_variable(
        variable_set=agent_id,
        name="test_variable",
        description="test variable",
        tool_id=tool_id,
        freshness_rules=None,
    )

    key = "yam_choock"
    data = {"zen_level": 9000}

    response = client.put(
        f"/agents/{agent_id}/variables/{variable.id}/{key}",
        json={"data": data},
    )

    variable_value = response.json()["variable_value"]
    assert variable_value["data"] == data
    assert "last_modified" in variable_value

    response = client.delete(f"/agents/{agent_id}/variables/{variable.id}/{key}")
    deleted_value_id = response.json()["variable_value_id"]
    assert deleted_value_id == variable_value["id"]

    response = client.get(f"/agents/{agent_id}/variables/{variable.id}/{key}")
    assert response.status_code == status.HTTP_404_NOT_FOUND
