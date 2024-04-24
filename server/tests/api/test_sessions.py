from typing import Any, Dict, Iterable
from fastapi.testclient import TestClient
from fastapi import status
from pytest import fixture
from datetime import datetime, timezone

from emcie.server.sessions import EventSource


@fixture
def session_id(client: TestClient) -> str:
    response = client.post("/sessions")
    return str(response.json()["session_id"])


def make_event_params(
    source: EventSource,
    data: Dict[str, Any] = {},
    type: str = "custom",
) -> Dict[str, Any]:
    return {
        "source": source,
        "type": type,
        "creation_utc": str(datetime.now(timezone.utc)),
        "data": data,
    }


def populate_session_id(
    client: TestClient,
    session_id: str,
    events: Iterable[Dict[str, Any]],
) -> None:
    for e in events:
        client.post(f"/sessions/{session_id}/events", json=e)


def event_is_according_to_params(event: Dict[str, Any], params: Dict[str, Any]) -> bool:
    tested_properties = ["source", "type", "data"]

    for p in tested_properties:
        if event[p] != params[p]:
            return False

    return True


def test_that_a_session_can_be_created(client: TestClient) -> None:
    response = client.post("/sessions")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "session_id" in data


def test_that_an_event_can_be_created(
    client: TestClient,
    session_id: str,
) -> None:
    response = client.post(
        f"/sessions/{session_id}/events",
        json=make_event_params("client"),
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "event_id" in data


def test_that_events_can_be_listed(
    client: TestClient,
    session_id: str,
) -> None:
    session_events = [
        make_event_params("client"),
        make_event_params("server"),
    ]

    populate_session_id(client, session_id, session_events)

    response = client.get(f"/sessions/{session_id}/events")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "events" in data

    assert len(data["events"]) == len(session_events)

    for event_params, listed_event in zip(session_events, data["events"]):
        assert event_is_according_to_params(event=listed_event, params=event_params)


def test_that_events_can_be_filtered_by_source(
    client: TestClient,
    session_id: str,
) -> None:
    session_events = [
        make_event_params("client"),
        make_event_params("server"),
        make_event_params("client"),
    ]

    populate_session_id(client, session_id, session_events)

    response = client.get(f"/sessions/{session_id}/events?source=client")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    session_client_events = [e for e in session_events if e["source"] == "client"]

    assert len(data["events"]) == len(session_client_events)

    for event_params, listed_event in zip(session_client_events, data["events"]):
        assert event_is_according_to_params(event=listed_event, params=event_params)
