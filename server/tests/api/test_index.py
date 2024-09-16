import asyncio
from fastapi.testclient import TestClient
from fastapi import status
from lagom import Container
from pytest import fixture

from emcie.server.core.agents import AgentId, AgentStore
from emcie.server.core.evaluations import EvaluationStore
from emcie.server.core.guidelines import GuidelineStore

from tests.core.services.indexing.test_evaluator import (
    AMOUNT_OF_TIME_TO_WAIT_FOR_EVALUATION_TO_START_RUNNING,
    TIME_TO_WAIT_PER_PAYLOAD,
)
from tests.test_utilities import SyncAwaiter


@fixture
def agent_id(
    container: Container,
    sync_await: SyncAwaiter,
) -> AgentId:
    store = container[AgentStore]
    agent = sync_await(store.create_agent(name="test-agent"))
    return agent.id


async def test_that_an_evaluation_can_be_created_and_fetched_with_completed_status(
    client: TestClient,
    container: Container,
    agent_id: AgentId,
) -> None:
    evaluation_store = container[EvaluationStore]

    response = client.post(
        "/index/evaluations",
        json={
            "agent_id": agent_id,
            "payloads": [
                {
                    "kind": "guideline",
                    "predicate": "the user greets you",
                    "action": "greet them back with 'Hello'",
                }
            ],
        },
    )

    assert response.status_code == status.HTTP_201_CREATED

    evaluation_id = response.json()["evaluation_id"]

    evaluation = await evaluation_store.read_evaluation(evaluation_id=evaluation_id)
    assert evaluation.id == evaluation_id

    await asyncio.sleep(TIME_TO_WAIT_PER_PAYLOAD)

    content = client.get(f"/index/evaluations/{evaluation_id}").raise_for_status().json()

    assert content["status"] == "completed"
    assert len(content["invoices"]) == 1
    invoice = content["invoices"][0]

    assert invoice["approved"]
    assert len(invoice["data"]["coherence_checks"]) == 0


async def test_that_an_evaluation_can_be_fetched_with_running_status(
    client: TestClient,
    agent_id: AgentId,
) -> None:
    evaluation_id = (
        client.post(
            "/index/evaluations",
            json={
                "agent_id": agent_id,
                "payloads": [
                    {
                        "kind": "guideline",
                        "predicate": "the user greets you",
                        "action": "greet them back with 'Hello'",
                    },
                    {
                        "kind": "guideline",
                        "predicate": "the user greeting you",
                        "action": "greet them back with 'Hola'",
                    },
                ],
            },
        )
        .raise_for_status()
        .json()["evaluation_id"]
    )

    await asyncio.sleep(AMOUNT_OF_TIME_TO_WAIT_FOR_EVALUATION_TO_START_RUNNING)

    content = client.get(f"/index/evaluations/{evaluation_id}").raise_for_status().json()

    assert content["status"] == "running"


async def test_that_an_evaluation_can_be_fetched_with_a_completed_status_containing_a_detailed_approved_invoice(
    client: TestClient,
    agent_id: AgentId,
) -> None:
    evaluation_id = (
        client.post(
            "/index/evaluations",
            json={
                "agent_id": agent_id,
                "payloads": [
                    {
                        "kind": "guideline",
                        "predicate": "the user greets you",
                        "action": "greet them back with 'Hello'",
                    }
                ],
            },
        )
        .raise_for_status()
        .json()["evaluation_id"]
    )

    await asyncio.sleep(AMOUNT_OF_TIME_TO_WAIT_FOR_EVALUATION_TO_START_RUNNING)

    content = client.get(f"/index/evaluations/{evaluation_id}").raise_for_status().json()

    assert content["status"] == "completed"

    assert len(content["invoices"]) == 1
    invoice = content["invoices"][0]

    assert invoice["approved"]
    assert len(invoice["data"]["coherence_checks"]) == 0


async def test_that_an_evaluation_can_be_fetched_with_a_completed_status_containing_a_detailed_unapproved_invoice(
    client: TestClient,
    agent_id: AgentId,
) -> None:
    evaluation_id = (
        client.post(
            "/index/evaluations",
            json={
                "agent_id": agent_id,
                "payloads": [
                    {
                        "kind": "guideline",
                        "predicate": "the user greets you",
                        "action": "greet them back with 'Hello'",
                    },
                    {
                        "kind": "guideline",
                        "predicate": "the user greeting you",
                        "action": "greet them back with 'Hola'",
                    },
                ],
            },
        )
        .raise_for_status()
        .json()["evaluation_id"]
    )

    await asyncio.sleep(TIME_TO_WAIT_PER_PAYLOAD * 2)

    content = client.get(f"/index/evaluations/{evaluation_id}").raise_for_status().json()

    assert content["status"] == "completed"

    assert len(content["invoices"]) == 2
    first_invoice = content["invoices"][0]

    assert not first_invoice["approved"]

    assert len(first_invoice["data"]["coherence_checks"]) >= 1


async def test_that_an_evaluation_can_be_fetched_with_a_detailed_approved_invoice_with_existing_guideline_connection_proposition(
    client: TestClient,
    container: Container,
    agent_id: AgentId,
) -> None:
    guideline_store = container[GuidelineStore]

    await guideline_store.create_guideline(
        guideline_set=agent_id,
        predicate="the user asks about the weather",
        action="provide the current weather update",
    )

    evaluation_id = (
        client.post(
            "/index/evaluations",
            json={
                "agent_id": agent_id,
                "payloads": [
                    {
                        "kind": "guideline",
                        "predicate": "providing the weather update",
                        "action": "mention the best time to go for a walk",
                    }
                ],
            },
        )
        .raise_for_status()
        .json()["evaluation_id"]
    )

    await asyncio.sleep(TIME_TO_WAIT_PER_PAYLOAD * 2)

    content = client.get(f"/index/evaluations/{evaluation_id}").raise_for_status().json()

    assert len(content["invoices"]) == 1
    invoice = content["invoices"][0]

    assert len(invoice["data"]["connection_propositions"]) == 1
    assert (
        invoice["data"]["connection_propositions"][0]["check_kind"]
        == "connection_with_existing_guideline"
    )

    assert (
        invoice["data"]["connection_propositions"][0]["source"]["predicate"]
        == "the user asks about the weather"
    )
    assert (
        invoice["data"]["connection_propositions"][0]["target"]["predicate"]
        == "providing the weather update"
    )


async def test_that_an_evaluation_can_be_fetched_with_a_detailed_approved_invoice_with_other_proposed_guideline_connection_proposition(
    client: TestClient,
    agent_id: AgentId,
) -> None:
    evaluation_id = (
        client.post(
            "/index/evaluations",
            json={
                "agent_id": agent_id,
                "payloads": [
                    {
                        "kind": "guideline",
                        "predicate": "the user asks about nearby restaurants",
                        "action": "provide a list of popular restaurants",
                    },
                    {
                        "kind": "guideline",
                        "predicate": "listing restaurants",
                        "action": "highlight the one with the best reviews",
                    },
                ],
            },
        )
        .raise_for_status()
        .json()["evaluation_id"]
    )

    await asyncio.sleep(TIME_TO_WAIT_PER_PAYLOAD * 2)

    content = client.get(f"/index/evaluations/{evaluation_id}").raise_for_status().json()

    assert content["status"] == "completed"

    assert len(content["invoices"]) == 2
    first_invoice = content["invoices"][0]

    assert first_invoice["data"]
    assert len(first_invoice["data"]["connection_propositions"]) == 1
    assert (
        first_invoice["data"]["connection_propositions"][0]["check_kind"]
        == "connection_with_another_evaluated_guideline"
    )

    assert (
        first_invoice["data"]["connection_propositions"][0]["source"]["predicate"]
        == "the user asks about nearby restaurants"
    )
    assert (
        first_invoice["data"]["connection_propositions"][0]["target"]["predicate"]
        == "listing restaurants"
    )


async def test_that_an_evaluation_failed_due_to_duplicate_guidelines_in_payloads_contains_relevant_error_message(
    client: TestClient,
    agent_id: AgentId,
) -> None:
    duplicate_payload = {
        "kind": "guideline",
        "predicate": "the user greets you",
        "action": "greet them back with 'Hello'",
    }

    response = client.post(
        "/index/evaluations",
        json={
            "agent_id": agent_id,
            "payloads": [
                duplicate_payload,
                duplicate_payload,
            ],
        },
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    data = response.json()

    assert "detail" in data
    assert data["detail"] == "Duplicate guideline found among the provided guidelines."


async def test_that_an_evaluation_failed_due_to_guideline_duplication_with_existing_guidelines_contains_relevant_error_message(
    client: TestClient,
    container: Container,
    agent_id: AgentId,
) -> None:
    guideline_store = container[GuidelineStore]

    await guideline_store.create_guideline(
        guideline_set=agent_id,
        predicate="the user greets you",
        action="greet them back with 'Hello'",
    )

    duplicate_payload = {
        "kind": "guideline",
        "predicate": "the user greets you",
        "action": "greet them back with 'Hello'",
    }

    response = client.post(
        "/index/evaluations",
        json={
            "agent_id": agent_id,
            "payloads": [
                duplicate_payload,
            ],
        },
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    data = response.json()

    assert (
        data["detail"]
        == f"Duplicate guideline found against existing guidelines: When the user greets you, then greet them back with 'Hello' in {agent_id} guideline_set"
    )


async def test_that_an_error_is_returned_when_no_payloads_are_provided(
    client: TestClient,
    agent_id: AgentId,
) -> None:
    response = client.post("/index/evaluations", json={"agent_id": agent_id, "payloads": []})

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    data = response.json()

    assert "detail" in data
    assert data["detail"] == "No payloads provided for the evaluation task."


async def test_that_an_error_is_returned_when_no_agent_id_provided(
    client: TestClient,
) -> None:
    response = client.post("/index/evaluations", json={"payloads": []})

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


async def test_that_an_evaluation_task_fails_if_another_task_is_already_running(
    client: TestClient,
    agent_id: AgentId,
) -> None:
    payloads = {
        "agent_id": agent_id,
        "payloads": [
            {
                "kind": "guideline",
                "predicate": "the user greets you",
                "action": "greet them back with 'Hello'",
            },
            {
                "kind": "guideline",
                "predicate": "the user asks about the weather",
                "action": "provide a weather update",
            },
        ],
    }

    first_evaluation_id = (
        client.post("/index/evaluations", json=payloads).raise_for_status().json()["evaluation_id"]
    )

    await asyncio.sleep(AMOUNT_OF_TIME_TO_WAIT_FOR_EVALUATION_TO_START_RUNNING)

    second_evaluation_id = (
        client.post("/index/evaluations", json=payloads).raise_for_status().json()["evaluation_id"]
    )

    content = client.get(f"/index/evaluations/{second_evaluation_id}").raise_for_status().json()

    assert content["status"] == "failed"
    assert content["error"] == f"An evaluation task '{first_evaluation_id}' is already running."
