from fastapi.testclient import TestClient
from fastapi import status
from lagom import Container

from emcie.server.evaluation_service import (
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
