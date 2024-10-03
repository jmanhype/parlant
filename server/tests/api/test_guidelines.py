from fastapi.testclient import TestClient
from fastapi import status
from lagom import Container

from emcie.server.core.agents import AgentId
from emcie.server.core.guideline_connections import ConnectionKind, GuidelineConnectionStore
from emcie.server.core.guidelines import GuidelineStore


async def test_that_a_guideline_can_be_created(
    client: TestClient,
    agent_id: AgentId,
) -> None:
    request_data = {
        "invoices": [
            {
                "payload": {
                    "kind": "guideline",
                    "predicate": "the user greets you",
                    "action": "greet them back with 'Hello'",
                },
                "checksum": "checksum_value",
                "approved": True,
                "data": {
                    "coherence_checks": [],
                    "connection_propositions": None,
                },
                "error": None,
            }
        ],
    }

    response = client.post(f"/agents/{agent_id}/guidelines/", json=request_data)
    assert response.status_code == status.HTTP_201_CREATED

    response_data = response.json()
    assert "guidelines" in response_data
    assert len(response_data["guidelines"]) == 1
    guideline = response_data["guidelines"][0]
    assert guideline["guideline_set"] == agent_id
    assert guideline["predicate"] == "the user greets you"
    assert guideline["action"] == "greet them back with 'Hello'"


async def test_that_a_guideline_can_be_deleted(
    client: TestClient,
    container: Container,
    agent_id: AgentId,
) -> None:
    guideline_store = container[GuidelineStore]

    guideline_to_delete = await guideline_store.create_guideline(
        guideline_set=agent_id,
        predicate="the user wants to unsubscribe",
        action="ask for confirmation",
    )

    content = (
        client.delete(f"/agents/{agent_id}/guidelines/{guideline_to_delete.id}")
        .raise_for_status()
        .json()
    )
    assert content["deleted_guideline_id"] == guideline_to_delete.id


async def test_that_unapproved_invoice_getting_rejected(
    client: TestClient,
    agent_id: AgentId,
) -> None:
    request_data = {
        "invoices": [
            {
                "payload": {
                    "kind": "guideline",
                    "predicate": "the user says goodbye",
                    "action": "say 'Goodbye' back",
                },
                "checksum": "checksum_value",
                "approved": False,
                "data": {"coherence_checks": [], "connection_propositions": []},
                "error": None,
            }
        ],
    }

    response = client.post("/agents/{agent_id}/guidelines/", json=request_data)
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    response_data = response.json()
    assert "detail" in response_data
    assert response_data["detail"] == "Unapproved invoice."


async def test_that_connection_between_two_introduced_guidelines_is_created_once(
    client: TestClient,
    container: Container,
    agent_id: AgentId,
) -> None:
    invoices = [
        {
            "payload": {
                "kind": "guideline",
                "predicate": "the user asks about nearby restaurants",
                "action": "provide a list of restaurants",
            },
            "checksum": "checksum1",
            "approved": True,
            "data": {
                "coherence_checks": [],
                "connection_propositions": [
                    {
                        "check_kind": "connection_with_another_evaluated_guideline",
                        "source": {
                            "predicate": "the user asks about nearby restaurants",
                            "action": "provide a list of restaurants",
                        },
                        "target": {
                            "predicate": "highlight the best-reviewed restaurant",
                            "action": "recommend the top choice",
                        },
                        "connection_kind": "entails",
                    }
                ],
            },
            "error": None,
        },
        {
            "payload": {
                "kind": "guideline",
                "predicate": "highlight the best-reviewed restaurant",
                "action": "recommend the top choice",
            },
            "checksum": "checksum2",
            "approved": True,
            "data": {
                "coherence_checks": [],
                "connection_propositions": [
                    {
                        "check_kind": "connection_with_another_evaluated_guideline",
                        "source": {
                            "predicate": "the user asks about nearby restaurants",
                            "action": "provide a list of restaurants",
                        },
                        "target": {
                            "predicate": "highlight the best-reviewed restaurant",
                            "action": "recommend the top choice",
                        },
                        "connection_kind": "entails",
                    }
                ],
            },
            "error": None,
        },
    ]

    guidelines = (
        client.post(
            f"/agents/{agent_id}/guidelines/",
            json={
                "invoices": invoices,
            },
        )
        .raise_for_status()
        .json()["guidelines"]
    )

    guideline_connection_store = container[GuidelineConnectionStore]
    connections = await guideline_connection_store.list_connections(
        indirect=False,
        source=guidelines[0]["id"],
    )

    connections = list(connections)

    assert len(connections) == 1
    connection = connections[0]

    assert connection.source == guidelines[0]["id"]
    assert connection.target == guidelines[1]["id"]


async def test_that_connection_between_existing_guideline_is_created(
    client: TestClient,
    container: Container,
    agent_id: AgentId,
) -> None:
    guideline_store = container[GuidelineStore]
    existing_guideline = await guideline_store.create_guideline(
        guideline_set=agent_id,
        predicate="the user asks about the weather",
        action="provide the current weather update",
    )

    invoice = {
        "payload": {
            "kind": "guideline",
            "predicate": "provide the current weather update",
            "action": "include temperature and humidity",
        },
        "checksum": "checksum_new",
        "approved": True,
        "data": {
            "coherence_checks": [],
            "connection_propositions": [
                {
                    "check_kind": "connection_with_existing_guideline",
                    "source": {
                        "predicate": "the user asks about the weather",
                        "action": "provide the current weather update",
                    },
                    "target": {
                        "predicate": "provide the current weather update",
                        "action": "include temperature and humidity",
                    },
                    "connection_kind": "entails",
                }
            ],
        },
        "error": None,
    }

    guideline = (
        client.post(
            f"/agents/{agent_id}/guidelines/",
            json={
                "invoices": [invoice],
            },
        )
        .raise_for_status()
        .json()["guidelines"][0]
    )

    guideline_connection_store = container[GuidelineConnectionStore]
    connections = await guideline_connection_store.list_connections(
        indirect=False,
        source=existing_guideline.id,
    )

    connections = list(connections)

    assert len(connections) == 1
    connection = connections[0]

    assert connection.source == existing_guideline.id
    assert connection.target == guideline["id"]


async def test_that_a_guideline_can_be_read_by_id(
    client: TestClient,
    container: Container,
    agent_id: AgentId,
) -> None:
    guideline_store = container[GuidelineStore]
    existing_guideline = await guideline_store.create_guideline(
        guideline_set=agent_id,
        predicate="the user asks about the weather",
        action="provide the current weather update",
    )

    guideline = (
        client.get(f"/agents/{agent_id}/guidelines/{existing_guideline.id}")
        .raise_for_status()
        .json()
    )

    assert guideline["guideline_set"] == agent_id
    assert guideline["id"] == existing_guideline.id
    assert guideline["predicate"] == "the user asks about the weather"
    assert guideline["action"] == "provide the current weather update"
    assert len(guideline["connections"]) == 0


async def test_that_guidelines_can_be_listed_for_an_agent(
    client: TestClient,
    container: Container,
    agent_id: AgentId,
) -> None:
    guideline_store = container[GuidelineStore]

    first = await guideline_store.create_guideline(
        guideline_set=agent_id,
        predicate="the user asks about the weather",
        action="provide the current weather update",
    )

    second = await guideline_store.create_guideline(
        guideline_set=agent_id,
        predicate="the user asks about pizza",
        action="provide what pizza is made of",
    )

    response = client.get(f"/agents/{agent_id}/guidelines/")
    assert response.status_code == status.HTTP_200_OK

    guidelines = response.json()["guidelines"]
    assert len(guidelines) == 2

    ids = [g["id"] for g in guidelines]

    assert first.id in ids
    assert second.id in ids


async def test_that_connections_can_be_added_to_guideline(
    client: TestClient,
    container: Container,
    agent_id: AgentId,
) -> None:
    guideline_store = container[GuidelineStore]
    guideline_connection_store = container[GuidelineConnectionStore]

    first = await guideline_store.create_guideline(
        guideline_set=agent_id,
        predicate="the user asks for help",
        action="provide assistance",
    )

    second = await guideline_store.create_guideline(
        guideline_set=agent_id,
        predicate="provide assistance",
        action="ask for clarification if needed",
    )

    patch_data = {
        "added_connections": [
            {
                "source": first.id,
                "target": second.id,
                "kind": "entails",
            }
        ],
    }

    response = client.patch(
        f"/agents/{agent_id}/guidelines/{first.id}",
        json=patch_data,
    )

    assert response.status_code == status.HTTP_200_OK

    connections = list(
        await guideline_connection_store.list_connections(
            indirect=False,
            source=first.id,
        )
    )

    assert len(connections) == 1
    connection = connections[0]

    assert connection.source == first.id
    assert connection.target == second.id
    assert connection.kind == ConnectionKind.ENTAILS

    response_data = response.json()
    assert "connections" in response_data
    assert len(response_data["connections"]) == 1
    response_connection = response_data["connections"][0]
    assert response_connection["source"]["id"] == first.id
    assert response_connection["target"]["id"] == second.id
    assert response_connection["kind"] == "entails"


async def test_that_connections_can_be_removed_from_guideline(
    client: TestClient,
    container: Container,
    agent_id: AgentId,
) -> None:
    guideline_store = container[GuidelineStore]
    guideline_connection_store = container[GuidelineConnectionStore]

    first = await guideline_store.create_guideline(
        guideline_set=agent_id,
        predicate="the user wants to unsubscribe",
        action="ask for confirmation",
    )

    second = await guideline_store.create_guideline(
        guideline_set=agent_id,
        predicate="ask for confirmation",
        action="provide unsubscribe link",
    )

    await guideline_connection_store.create_connection(
        source=first.id,
        target=second.id,
        kind=ConnectionKind.SUGGESTS,
    )

    patch_data = {
        "added_connections": None,
        "removed_connections": [second.id],
    }

    response = client.patch(
        f"/agents/{agent_id}/guidelines/{first.id}",
        json=patch_data,
    )

    assert response.status_code == status.HTTP_200_OK

    connections = await guideline_connection_store.list_connections(
        indirect=False,
        source=first.id,
    )

    connections = list(connections)
    assert len(connections) == 0

    response_data = response.json()
    assert "connections" in response_data
    assert len(response_data["connections"]) == 0


async def test_that_read_guideline_contains_indirect_and_direct_connections(
    client: TestClient,
    container: Container,
    agent_id: AgentId,
) -> None:
    guideline_store = container[GuidelineStore]
    guideline_connection_store = container[GuidelineConnectionStore]

    first = await guideline_store.create_guideline(
        guideline_set=agent_id,
        predicate="the user asks for help",
        action="provide assistance",
    )

    second = await guideline_store.create_guideline(
        guideline_set=agent_id,
        predicate="provide assistance",
        action="ask for clarification if needed",
    )

    third = await guideline_store.create_guideline(
        guideline_set=agent_id,
        predicate="ask for clarification if needed",
        action="clarify the user's request",
    )

    fourth = await guideline_store.create_guideline(
        guideline_set=agent_id,
        predicate="clarify the user's request",
        action="provide a suitable response",
    )

    fifth = await guideline_store.create_guideline(
        guideline_set=agent_id,
        predicate="provide a suitable response",
        action="ensure the response is clear",
    )

    await guideline_connection_store.create_connection(
        source=first.id, target=second.id, kind=ConnectionKind.ENTAILS
    )

    await guideline_connection_store.create_connection(
        source=second.id, target=third.id, kind=ConnectionKind.ENTAILS
    )

    await guideline_connection_store.create_connection(
        source=third.id, target=fourth.id, kind=ConnectionKind.ENTAILS
    )

    await guideline_connection_store.create_connection(
        source=fourth.id, target=fifth.id, kind=ConnectionKind.ENTAILS
    )

    guideline = client.get(f"/agents/{agent_id}/guidelines/{third.id}").raise_for_status().json()

    assert len(guideline["connections"]) == 4
    connections = guideline["connections"]

    assert any(
        c["source"]["id"] == first.id
        and c["target"]["id"] == second.id
        and c["source"]["predicate"] == first.content.predicate
        and c["source"]["action"] == first.content.action
        and c["target"]["predicate"] == second.content.predicate
        and c["target"]["action"] == second.content.action
        and c["indirect"] is True
        for c in connections
    )

    assert any(
        c["source"]["id"] == second.id
        and c["target"]["id"] == third.id
        and c["source"]["predicate"] == second.content.predicate
        and c["source"]["action"] == second.content.action
        and c["target"]["predicate"] == third.content.predicate
        and c["target"]["action"] == third.content.action
        and c["indirect"] is False
        for c in connections
    )

    assert any(
        c["source"]["id"] == third.id
        and c["target"]["id"] == fourth.id
        and c["source"]["predicate"] == third.content.predicate
        and c["source"]["action"] == third.content.action
        and c["target"]["predicate"] == fourth.content.predicate
        and c["target"]["action"] == fourth.content.action
        and c["indirect"] is False
        for c in connections
    )

    assert any(
        c["source"]["id"] == fourth.id
        and c["target"]["id"] == fifth.id
        and c["source"]["predicate"] == fourth.content.predicate
        and c["source"]["action"] == fourth.content.action
        and c["target"]["predicate"] == fifth.content.predicate
        and c["target"]["action"] == fifth.content.action
        and c["indirect"] is True
        for c in connections
    )
