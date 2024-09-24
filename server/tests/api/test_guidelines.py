from fastapi.testclient import TestClient
from fastapi import status
from lagom import Container

from emcie.server.core.agents import AgentId
from emcie.server.core.guideline_connections import GuidelineConnectionStore
from emcie.server.core.guidelines import GuidelineStore


async def test_that_a_guideline_can_be_created(
    client: TestClient,
    agent_id: AgentId,
) -> None:
    request_data = {
        "agent_id": agent_id,
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

    response = client.post("/guidelines", json=request_data)
    assert response.status_code == status.HTTP_201_CREATED

    response_data = response.json()
    assert "guidelines" in response_data
    assert len(response_data["guidelines"]) == 1
    guideline = response_data["guidelines"][0]
    assert guideline["guideline_set"] == agent_id
    assert guideline["predicate"] == "the user greets you"
    assert guideline["action"] == "greet them back with 'Hello'"


async def test_that_unapproved_invoice_getting_rejected(
    client: TestClient,
    agent_id: AgentId,
) -> None:
    request_data = {
        "agent_id": agent_id,
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

    response = client.post("/guidelines", json=request_data)
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
            "/guidelines",
            json={
                "agent_id": agent_id,
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
            "/guidelines",
            json={
                "agent_id": agent_id,
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

    read_response = client.get(f"/guidelines/{agent_id}/{existing_guideline.id}")
    assert read_response.status_code == status.HTTP_200_OK

    read_guideline = read_response.json()
    assert read_guideline["guideline_set"] == agent_id
    assert read_guideline["id"] == existing_guideline.id
    assert read_guideline["predicate"] == "the user asks about the weather"
    assert read_guideline["action"] == "provide the current weather update"


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

    response = client.get(f"/guidelines/{agent_id}")
    assert response.status_code == status.HTTP_200_OK

    guidelines = response.json()["guidelines"]
    assert len(guidelines) == 2

    ids = [g["id"] for g in guidelines]

    assert first.id in ids
    assert second.id in ids
