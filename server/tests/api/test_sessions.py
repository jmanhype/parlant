import time
from typing import Any
from fastapi.testclient import TestClient
from fastapi import status
from lagom import Container
from pytest import fixture, mark
from datetime import datetime, timezone
from itertools import count

from emcie.server.core.agents import AgentId
from emcie.server.core.sessions import EventSource, SessionId, SessionStore


@fixture
def agent_id(client: TestClient) -> AgentId:
    response = client.post(
        "/agents",
        json={"agent_name": "test-agent"},
    )
    return AgentId(response.json()["agent_id"])


@fixture
def session_id(
    client: TestClient,
    agent_id: AgentId,
) -> SessionId:
    response = client.post(
        "/sessions",
        json={
            "end_user_id": "test_user",
            "agent_id": agent_id,
        },
    )
    return SessionId(response.json()["session_id"])


@fixture
async def long_session_id(
    client: TestClient,
    container: Container,
    agent_id: AgentId,
) -> SessionId:
    response = client.post(
        "/sessions",
        json={
            "end_user_id": "test_user",
            "agent_id": agent_id,
        },
    )
    session_id = SessionId(response.json()["session_id"])

    await populate_session_id(
        container,
        session_id,
        [
            make_event_params("client"),
            make_event_params("server"),
            make_event_params("client"),
            make_event_params("server"),
            make_event_params("server"),
            make_event_params("client"),
        ],
    )

    return session_id


def make_event_params(
    source: EventSource,
    data: dict[str, Any] = {},
    kind: str = "custom",
) -> dict[str, Any]:
    return {
        "source": source,
        "kind": kind,
        "creation_utc": str(datetime.now(timezone.utc)),
        "data": data,
    }


async def populate_session_id(
    container: Container,
    session_id: SessionId,
    events: list[dict[str, Any]],
) -> None:
    session_store = container[SessionStore]

    for e in events:
        await session_store.create_event(
            session_id=session_id,
            source=e["source"],
            kind=e["kind"],
            data=e["data"],
        )


def event_is_according_to_params(
    event: dict[str, Any],
    params: dict[str, Any],
) -> bool:
    tested_properties = ["source", "kind", "data"]

    for p in tested_properties:
        if event[p] != params[p]:
            return False

    return True


def test_that_a_session_can_be_created(
    client: TestClient,
    agent_id: AgentId,
) -> None:
    response = client.post(
        "/sessions",
        json={
            "end_user_id": "test_user",
            "agent_id": agent_id,
        },
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    assert "session_id" in data
    assert "title" in data
    assert data["title"] is None


def test_that_a_session_can_be_created_with_title(
    client: TestClient,
    agent_id: AgentId,
) -> None:
    title = "Test Session Title"

    response = client.post(
        "/sessions",
        json={
            "end_user_id": "test_user",
            "agent_id": agent_id,
            "title": title,
        },
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    assert "session_id" in data
    assert data["title"] == title


def test_that_sessions_can_be_listed(
    client: TestClient,
    agent_id: AgentId,
) -> None:
    client.post(
        "/sessions",
        json={
            "end_user_id": "test_user1",
            "agent_id": agent_id,
            "title": "Test Session1 Title",
        },
    )

    client.post(
        "/sessions",
        json={
            "end_user_id": "test_user2",
            "agent_id": agent_id,
            "title": "Test Session2 Title",
        },
    )

    client.post(
        "/sessions",
        json={
            "end_user_id": "test_user2",
            "agent_id": agent_id,
            "title": "Test Session2 Title",
        },
    )

    response = client.get(f"/sessions/?agent_id={agent_id}")

    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    assert data

    sessions = data["sessions"]

    assert len(sessions) == 3

    assert sessions[0]["title"] == "Test Session1 Title"
    assert sessions[1]["title"] == "Test Session2 Title"
    assert sessions[2]["title"] == "Test Session2 Title"

    assert sessions[0]["end_user_id"] == "test_user1"
    assert sessions[1]["end_user_id"] == "test_user2"
    assert sessions[2]["end_user_id"] == "test_user2"


def test_that_sessions_can_be_listed(
    client: TestClient,
    agent_id: AgentId,
) -> None:
    client.post(
        "/sessions",
        json={
            "end_user_id": "test_user1",
            "agent_id": agent_id,
            "title": "Test Session1 Title",
        },
    )

    client.post(
        "/sessions",
        json={
            "end_user_id": "test_user2",
            "agent_id": agent_id,
            "title": "Test Session2 Title",
        },
    )

    client.post(
        "/sessions",
        json={
            "end_user_id": "test_user2",
            "agent_id": agent_id,
            "title": "Test Session2 Title",
        },
    )

    response = client.get(f"/sessions/?agent_id={agent_id}")

    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    assert data

    sessions = data["sessions"]

    assert len(sessions) == 3

    assert sessions[0]["title"] == "Test Session1 Title"
    assert sessions[1]["title"] == "Test Session2 Title"
    assert sessions[2]["title"] == "Test Session2 Title"

    assert sessions[0]["end_user_id"] == "test_user1"
    assert sessions[1]["end_user_id"] == "test_user2"
    assert sessions[2]["end_user_id"] == "test_user2"


async def test_that_events_can_be_listed(
    client: TestClient,
    container: Container,
    session_id: SessionId,
) -> None:
    session_events = [
        make_event_params("client"),
        make_event_params("server"),
        make_event_params("server"),
        make_event_params("client"),
        make_event_params("server"),
    ]

    await populate_session_id(container, session_id, session_events)

    response = client.get(f"/sessions/{session_id}/events")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "events" in data

    assert len(data["events"]) == len(session_events)

    for i, event_params, listed_event in zip(count(), session_events, data["events"]):
        assert listed_event["offset"] == i
        assert event_is_according_to_params(event=listed_event, params=event_params)


def test_that_a_session_is_created_with_zeroed_out_consumption_offsets(
    client: TestClient,
    long_session_id: SessionId,
) -> None:
    response = client.get(f"/sessions/{long_session_id}")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    assert "consumption_offsets" in data
    assert "client" in data["consumption_offsets"]
    assert data["consumption_offsets"]["client"] == 0


@mark.parametrize("consumer_id", ["client"])
def test_that_consumption_offsets_can_be_updated(
    client: TestClient,
    long_session_id: SessionId,
    consumer_id: str,
) -> None:
    response = client.patch(
        f"/sessions/{long_session_id}",
        json={
            "consumption_offsets": {
                consumer_id: 1,
            }
        },
    )
    assert response.status_code == status.HTTP_204_NO_CONTENT

    response = client.get(f"/sessions/{long_session_id}")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    assert data["consumption_offsets"][consumer_id] == 1


@mark.parametrize("offset", (0, 2, 4))
async def test_that_events_can_be_filtered_by_offset(
    client: TestClient,
    container: Container,
    session_id: SessionId,
    offset: int,
) -> None:
    session_events = [
        make_event_params("client"),
        make_event_params("server"),
        make_event_params("client"),
        make_event_params("server"),
        make_event_params("client"),
    ]

    await populate_session_id(container, session_id, session_events)

    retrieved_events = (
        client.get(
            f"/sessions/{session_id}/events",
            params={
                "min_offset": offset,
            },
        )
        .raise_for_status()
        .json()["events"]
    )

    for event_params, listed_event in zip(session_events, retrieved_events):
        assert event_is_according_to_params(event=listed_event, params=event_params)


def test_that_posting_a_message_elicits_a_response(
    client: TestClient,
    session_id: SessionId,
) -> None:
    posted_event = (
        client.post(
            f"/sessions/{session_id}/events",
            json={"content": "Hello there!"},
        )
        .raise_for_status()
        .json()
    )

    events_in_session = (
        client.get(
            f"/sessions/{session_id}/events",
            params={
                "min_offset": posted_event["event_offset"] + 1,
                "wait": True,
            },
        )
        .raise_for_status()
        .json()["events"]
    )

    assert events_in_session


def test_that_not_waiting_for_a_response_does_in_fact_return_immediately(
    client: TestClient,
    agent_id: AgentId,
    session_id: SessionId,
) -> None:
    posted_event = (
        client.post(
            f"/sessions/{session_id}/events",
            json={"content": "Hello there!"},
        )
        .raise_for_status()
        .json()
    )

    t_start = time.time()

    client.get(
        f"/sessions/{session_id}/events",
        params={
            "min_offset": posted_event["event_offset"] + 1,
            "wait": False,
        },
    )

    t_end = time.time()

    assert (t_end - t_start) < 0.25
