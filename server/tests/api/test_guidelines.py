from fastapi.testclient import TestClient
from fastapi import status
from lagom import Container

from emcie.server.core.agents import AgentId
from emcie.server.core.guideline_connections import ConnectionKind, GuidelineConnectionStore
from emcie.server.core.guidelines import Guideline, GuidelineContent, GuidelineStore


async def create_and_connect(
    container: Container,
    agent_id: AgentId,
    guideline_contents: list[GuidelineContent],
) -> list[Guideline]:
    guidelines = [
        await container[GuidelineStore].create_guideline(
            guideline_set=agent_id,
            predicate=gc.predicate,
            action=gc.action,
        )
        for gc in guideline_contents
    ]

    for source, target in zip(guidelines, guidelines[1:]):
        await container[GuidelineConnectionStore].create_connection(
            source=source.id, target=target.id, kind=ConnectionKind.ENTAILS
        )

    return guidelines


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
    items = response.json()["items"]

    assert len(items) == 1
    assert items[0]["guideline"]["predicate"] == "the user greets you"
    assert items[0]["guideline"]["action"] == "greet them back with 'Hello'"


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
    assert content["guideline_id"] == guideline_to_delete.id


async def test_that_an_unapproved_invoice_is_rejected(
    client: TestClient,
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


async def test_that_a_connection_between_two_introduced_guidelines_is_created(
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

    items = (
        client.post(
            f"/agents/{agent_id}/guidelines/",
            json={
                "invoices": invoices,
            },
        )
        .raise_for_status()
        .json()["items"]
    )

    connections = await container[GuidelineConnectionStore].list_connections(
        indirect=False,
        source=items[0]["guideline"]["id"],
    )

    assert len(connections) == 1
    assert connections[0].source == items[0]["guideline"]["id"]
    assert connections[0].target == items[1]["guideline"]["id"]


async def test_that_a_connection_to_an_existing_guideline_is_created(
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

    introduced_guideline = (
        client.post(
            f"/agents/{agent_id}/guidelines/",
            json={
                "invoices": [invoice],
            },
        )
        .raise_for_status()
        .json()["items"][0]["guideline"]
    )

    connections = await container[GuidelineConnectionStore].list_connections(
        indirect=False,
        source=existing_guideline.id,
    )

    assert len(connections) == 1
    assert connections[0].source == existing_guideline.id
    assert connections[0].target == introduced_guideline["id"]


async def test_that_a_guideline_can_be_read_by_id(
    client: TestClient,
    container: Container,
    agent_id: AgentId,
) -> None:
    guideline_store = container[GuidelineStore]

    stored_guideline = await guideline_store.create_guideline(
        guideline_set=agent_id,
        predicate="the user asks about the weather",
        action="provide the current weather update",
    )

    item = (
        client.get(f"/agents/{agent_id}/guidelines/{stored_guideline.id}").raise_for_status().json()
    )

    assert item["guideline"]["id"] == stored_guideline.id
    assert item["guideline"]["predicate"] == "the user asks about the weather"
    assert item["guideline"]["action"] == "provide the current weather update"
    assert len(item["connections"]) == 0


async def test_that_guidelines_can_be_listed_for_an_agent(
    client: TestClient,
    container: Container,
    agent_id: AgentId,
) -> None:
    stored_guidelines = await create_and_connect(
        container,
        agent_id,
        [
            GuidelineContent("A", "B"),
            GuidelineContent("B", "C"),
        ],
    )

    response_guidelines = (
        client.get(f"/agents/{agent_id}/guidelines/").raise_for_status().json()["guidelines"]
    )

    assert len(response_guidelines) == 2
    assert any(stored_guidelines[0].id == g["id"] for g in response_guidelines)
    assert any(stored_guidelines[1].id == g["id"] for g in response_guidelines)


async def test_that_a_connection_can_be_added_to_a_guideline(
    client: TestClient,
    container: Container,
    agent_id: AgentId,
) -> None:
    guidelines = await create_and_connect(
        container,
        agent_id,
        [
            GuidelineContent("A", "B"),
            GuidelineContent("B", "C"),
        ],
    )

    response_connections = (
        client.patch(
            f"/agents/{agent_id}/guidelines/{guidelines[0].id}",
            json={
                "added_connections": [
                    {
                        "source": guidelines[0].id,
                        "target": guidelines[1].id,
                        "kind": "entails",
                    }
                ],
            },
        )
        .raise_for_status()
        .json()["connections"]
    )

    stored_connections = list(
        await container[GuidelineConnectionStore].list_connections(
            indirect=False,
            source=guidelines[0].id,
        )
    )

    assert len(stored_connections) == 1
    assert stored_connections[0].source == guidelines[0].id
    assert stored_connections[0].target == guidelines[1].id
    assert stored_connections[0].kind == ConnectionKind.ENTAILS

    assert len(response_connections) == 1
    assert response_connections[0]["source"]["id"] == guidelines[0].id
    assert response_connections[0]["target"]["id"] == guidelines[1].id
    assert response_connections[0]["kind"] == "entails"


async def test_that_a_direct_target_connection_can_be_removed_from_a_guideline(
    client: TestClient,
    container: Container,
    agent_id: AgentId,
) -> None:
    guidelines = await create_and_connect(
        container,
        agent_id,
        [
            GuidelineContent("A", "B"),
            GuidelineContent("B", "C"),
        ],
    )

    response_collections = (
        client.patch(
            f"/agents/{agent_id}/guidelines/{guidelines[0].id}",
            json={
                "removed_connections": [guidelines[1].id],
            },
        )
        .raise_for_status()
        .json()["connections"]
    )

    assert len(response_collections) == 0

    stored_connections = await container[GuidelineConnectionStore].list_connections(
        indirect=True,
        source=guidelines[0].id,
    )

    assert len(stored_connections) == 0


async def test_that_an_indirect_connection_cannot_be_removed_from_a_guideline(
    client: TestClient,
    container: Container,
    agent_id: AgentId,
) -> None:
    guidelines = await create_and_connect(
        container,
        agent_id,
        [
            GuidelineContent("A", "B"),
            GuidelineContent("B", "C"),
            GuidelineContent("C", "D"),
        ],
    )

    response = client.patch(
        f"/agents/{agent_id}/guidelines/{guidelines[0].id}",
        json={
            "removed_connections": [guidelines[2].id],
        },
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    stored_connections = await container[GuidelineConnectionStore].list_connections(
        indirect=True,
        source=guidelines[0].id,
    )

    assert len(stored_connections) == 2


async def test_that_deleting_a_guideline_also_deletes_all_of_its_direct_connections(
    client: TestClient,
    container: Container,
    agent_id: AgentId,
) -> None:
    guidelines = await create_and_connect(
        container,
        agent_id,
        [
            GuidelineContent("A", "B"),
            GuidelineContent("B", "C"),
        ],
    )

    client.delete(f"/agents/{agent_id}/guidelines/{guidelines[0].id}").raise_for_status()

    stored_connections = await container[GuidelineConnectionStore].list_connections(
        indirect=False,
        source=guidelines[0].id,
    )

    assert not stored_connections


async def test_that_reading_a_guideline_lists_both_direct_and_indirect_connections(
    client: TestClient,
    container: Container,
    agent_id: AgentId,
) -> None:
    guidelines = [
        await container[GuidelineStore].create_guideline(
            guideline_set=agent_id,
            predicate=predicate,
            action=action,
        )
        for predicate, action in [
            ("A", "B"),
            ("B", "C"),
            ("C", "D"),
            ("D", "E"),
            ("E", "F"),
        ]
    ]

    for source, target in zip(guidelines, guidelines[1:]):
        await container[GuidelineConnectionStore].create_connection(
            source=source.id, target=target.id, kind=ConnectionKind.ENTAILS
        )

    third_item = (
        client.get(f"/agents/{agent_id}/guidelines/{guidelines[2].id}").raise_for_status().json()
    )

    assert 2 == len([c for c in third_item["connections"] if c["indirect"]])
    assert 2 == len([c for c in third_item["connections"] if not c["indirect"]])

    connections = sorted(third_item["connections"], key=lambda c: c["source"]["predicate"])

    for i, c in enumerate(connections):
        guideline_a = guidelines[i]
        guideline_b = guidelines[i + 1]

        assert c["source"] == {
            "id": guideline_a.id,
            "predicate": guideline_a.content.predicate,
            "action": guideline_a.content.action,
        }

        assert c["target"] == {
            "id": guideline_b.id,
            "predicate": guideline_b.content.predicate,
            "action": guideline_b.content.action,
        }

        is_direct = third_item["guideline"]["id"] in (c["source"]["id"], c["target"]["id"])
        assert c["indirect"] is not is_direct
