from fastapi import status
from fastapi.testclient import TestClient
from lagom import Container

from emcie.server.core.agents import AgentId
from emcie.server.core.guideline_connections import ConnectionKind, GuidelineConnectionStore
from emcie.server.core.guidelines import GuidelineStore


async def test_that_a_connection_can_be_added_between_guidelines(
    client: TestClient,
    container: Container,
    agent_id: AgentId,
) -> None:
    guideline_store = container[GuidelineStore]

    source = await guideline_store.create_guideline(
        guideline_set=agent_id,
        predicate="the user asks about the time",
        action="tell them the current time",
    )

    target = await guideline_store.create_guideline(
        guideline_set=agent_id,
        predicate="the user asks for the date",
        action="tell them the current date",
    )

    response = client.post(
        "/connections",
        json={
            "source_guideline_id": source.id,
            "target_guideline_id": target.id,
            "kind": "entails",
        },
    )

    assert response.status_code == status.HTTP_201_CREATED

    connection_data = response.json()
    assert connection_data["source"] == source.id
    assert connection_data["target"] == target.id
    assert connection_data["kind"] == "entails"
    assert "id" in connection_data

    guideline_connection_store = container[GuidelineConnectionStore]
    connections = await guideline_connection_store.list_connections(
        indirect=False,
        source=source.id,
    )

    connections = list(connections)
    assert len(connections) == 1
    connection = connections[0]
    assert connection.source == source.id
    assert connection.target == target.id
    assert connection.kind == ConnectionKind.ENTAILS


async def test_that_connections_can_be_listed_for_an_agent(
    client: TestClient,
    container: Container,
    agent_id: AgentId,
) -> None:
    guideline_store = container[GuidelineStore]

    first = await guideline_store.create_guideline(
        guideline_set=agent_id,
        predicate="the user asks for a joke",
        action="tell them a joke",
    )

    second = await guideline_store.create_guideline(
        guideline_set=agent_id,
        predicate="tell them a joke",
        action="provide a funny joke",
    )

    third = await guideline_store.create_guideline(
        guideline_set=agent_id,
        predicate="provide a funny joke",
        action="make sure it's appropriate",
    )

    guideline_connection_store = container[GuidelineConnectionStore]
    await guideline_connection_store.update_connection(
        source=first.id,
        target=second.id,
        kind=ConnectionKind.ENTAILS,
    )

    await guideline_connection_store.update_connection(
        source=second.id,
        target=third.id,
        kind=ConnectionKind.SUGGESTS,
    )

    response = client.get(f"/connections?source_guideline_id={first.id}")
    assert response.status_code == status.HTTP_200_OK

    connections_data = response.json()["connections"]
    assert len(connections_data) == 1
    connection = connections_data[0]
    assert connection["source"] == first.id
    assert connection["target"] == second.id
    assert connection["kind"] == "entails"

    response = client.get(f"/connections?source_guideline_id={first.id}&indirect=true")
    assert response.status_code == status.HTTP_200_OK

    connections_data = response.json()["connections"]
    assert len(connections_data) == 2
    connection_ids = {(c["source"], c["target"]) for c in connections_data}
    expected_connections = {
        (first.id, second.id),
        (second.id, third.id),
    }
    assert connection_ids == expected_connections
