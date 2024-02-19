from typing import AsyncIterator
from fastapi import status
from fastapi.testclient import TestClient
from pytest import fixture

from emcie.server import main


@fixture
async def client() -> AsyncIterator[TestClient]:
    app = await main.create_app()

    with TestClient(app) as client:
        yield client


@fixture
def agent_id(client: TestClient) -> str:
    return str(client.post("/agents").json()["agent_id"])


@fixture
def new_thread_id(client: TestClient) -> str:
    return str(client.post("/threads").json()["thread_id"])


@fixture
def user_question_thread_id(
    client: TestClient,
    new_thread_id: str,
) -> str:
    response = client.post(
        f"/threads/{new_thread_id}/messages",
        json={
            "role": "user",
            "content": "Is 42 a number?",
        },
    )

    assert response.status_code == status.HTTP_200_OK

    return new_thread_id
