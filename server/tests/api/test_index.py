import asyncio
from fastapi.testclient import TestClient
from fastapi import status
from lagom import Container

from emcie.server.behavioral_change_evaluation import (
    BehavioralChangeEvaluator,
    EvaluationStore,
)


async def test_that_an_evaluation_can_be_created(
    client: TestClient,
    container: Container,
) -> None:
    evaluation_store = container[EvaluationStore]

    payloads = {
        "payloads": [
            {
                "type": "guideline",
                "guideline_set": "test-agent",
                "predicate": "the user greets you",
                "content": "greet them back with 'Hello'",
            }
        ]
    }

    response = client.post("/index/evaluations", json=payloads)

    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    assert "evaluation_id" in data

    evaluation = await evaluation_store.read_evaluation(evaluation_id=data["evaluation_id"])
    assert evaluation.id == data["evaluation_id"]


def test_that_an_error_is_returned_when_no_payloads_are_provided(
    client: TestClient,
) -> None:
    response = client.post("/index/evaluations", json={"payloads": []})

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    data = response.json()

    assert "detail" in data
    assert data["detail"] == "No payloads provided for the evaluation task."


async def test_that_an_evaluation_can_be_fetched_with_running_status(
    client: TestClient,
) -> None:
    payloads = {
        "payloads": [
            {
                "type": "guideline",
                "guideline_set": "test-agent",
                "predicate": "the user greets you",
                "content": "greet them back with 'Hello'",
            },
            {
                "type": "guideline",
                "guideline_set": "test-agent",
                "predicate": "the user greeting you",
                "content": "greet them back with 'Hola'",
            },
        ]
    }

    response = client.post("/index/evaluations", json=payloads)
    assert response.status_code == status.HTTP_200_OK
    evaluation_id = response.json()["evaluation_id"]

    reasonable_time_for_task_start_to_run = 0.25
    await asyncio.sleep(reasonable_time_for_task_start_to_run)

    get_response = client.get(f"/index/evaluations/{evaluation_id}")
    assert get_response.status_code == status.HTTP_200_OK
    assert get_response.json()["status"] == "running"


async def test_that_an_evaluation_can_be_fetched_with_a_completed_status_containing_a_detailed_approved_invoice(
    client: TestClient,
    container: Container,
) -> None:
    evaluation_service = container[BehavioralChangeEvaluator]

    payloads = {
        "payloads": [
            {
                "type": "guideline",
                "guideline_set": "test-agent",
                "predicate": "the user greets you",
                "content": "greet them back with 'Hello'",
            }
        ]
    }

    response = client.post("/index/evaluations", json=payloads)
    assert response.status_code == status.HTTP_200_OK
    evaluation_id = response.json()["evaluation_id"]

    reasonable_time_for_task_start_to_run = 0.25
    await asyncio.sleep(reasonable_time_for_task_start_to_run)

    get_response = client.get(f"/index/evaluations/{evaluation_id}")
    assert get_response.status_code == status.HTTP_200_OK

    content = get_response.json()

    assert content["status"] == "completed"

    assert len(content["items"]) == 1
    item = content["items"][0]

    assert item["invoice"]["approved"]
    assert item["invoice"]["checksum"] == evaluation_service._generate_checksum(item["payload"])

    assert item["invoice"]["data"]["detail"]["type"] == "coherence_check"
    assert len(item["invoice"]["data"]["detail"]["data"]) == 0


async def test_that_an_evaluation_can_be_fetched_with_a_completed_status_containing_a_detailed_unapproved_invoice(
    client: TestClient,
) -> None:
    payloads = {
        "payloads": [
            {
                "type": "guideline",
                "guideline_set": "test-agent",
                "predicate": "the user greets you",
                "content": "greet them back with 'Hello'",
            },
            {
                "type": "guideline",
                "guideline_set": "test-agent",
                "predicate": "the user greeting you",
                "content": "greet them back with 'Hola'",
            },
        ]
    }

    response = client.post("/index/evaluations", json=payloads)
    assert response.status_code == status.HTTP_200_OK
    evaluation_id = response.json()["evaluation_id"]

    reasonable_time_for_task_to_complete = 5
    await asyncio.sleep(reasonable_time_for_task_to_complete)

    get_response = client.get(f"/index/evaluations/{evaluation_id}")
    assert get_response.status_code == status.HTTP_200_OK

    content = get_response.json()

    assert content["status"] == "completed"

    assert len(content["items"]) == 2
    first_item = content["items"][0]

    assert not first_item["invoice"]["approved"]

    assert first_item["invoice"]["data"]["detail"]["type"] == "coherence_check"
    assert len(first_item["invoice"]["data"]["detail"]["data"]) >= 1


async def test_that_an_evaluation_can_be_fetched_with_a_failed_status_due_to_duplicate_guidelines_in_payloads_conaints_relevant_error_message(
    client: TestClient,
    container: Container,
) -> None:
    duplicate_payload = {
        "type": "guideline",
        "guideline_set": "test-agent",
        "predicate": "the user greets you",
        "content": "greet them back with 'Hello'",
    }

    response = client.post(
        "/index/evaluations",
        json={
            "payloads": [
                duplicate_payload,
                duplicate_payload,
            ]
        },
    )

    assert response.status_code == status.HTTP_200_OK
    evaluation_id = response.json()["evaluation_id"]

    reasonable_time_for_task_to_complete = 2
    await asyncio.sleep(reasonable_time_for_task_to_complete)

    get_response = client.get(f"/index/evaluations/{evaluation_id}")
    assert get_response.status_code == status.HTTP_200_OK

    content = get_response.json()

    assert content["status"] == "failed"
    assert content["error"] == "Duplicate guideline found among the provided guidelines."
