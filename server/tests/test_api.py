from datetime import datetime
from dateutil import parser
from fastapi.testclient import TestClient
from pytest import fixture, mark

from emcie.server import main


@fixture
def client() -> TestClient:
    app = main.create_app()
    return TestClient(app)


@fixture
async def new_thread_id(client: TestClient) -> str:
    return str(client.post("/threads").json()["thread_id"])


def test_that_a_thread_can_be_created(
    client: TestClient,
) -> None:
    response = client.post("/threads")
    assert response.status_code == 200
    data = response.json()
    assert "thread_id" in data


@mark.asyncio
@mark.parametrize("role", ("user", "assistant"))
async def test_that_a_user_message_can_be_added_to_a_thread(
    client: TestClient,
    new_thread_id: str,
    role: str,
) -> None:
    before_creating_the_message = datetime.utcnow()

    response = client.post(
        f"/threads/{new_thread_id}/messages",
        json={
            "role": role,
            "content": "Hello",
        },
    )

    assert response.status_code == 200

    response = client.get(f"/threads/{new_thread_id}/messages")

    assert response.status_code == 200

    data = response.json()

    assert len(data["messages"]) == 1
    assert data["messages"][0]["role"] == role
    assert data["messages"][0]["content"] == "Hello"
    assert parser.parse(data["messages"][0]["creation_utc"]) >= before_creating_the_message
