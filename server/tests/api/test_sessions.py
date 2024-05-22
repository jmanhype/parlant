from typing import Any, Dict, Iterable
from fastapi.testclient import TestClient
from fastapi import status
from pytest import fixture, mark
from datetime import datetime, timezone
from itertools import count

from emcie.server.core.sessions import EventSource, SessionId


@fixture
def session_id(client: TestClient) -> SessionId:
    response = client.post("/sessions", json={"client_id": "my_client"})
    return SessionId(response.json()["session_id"])


@fixture
def long_session_id(client: TestClient) -> SessionId:
    response = client.post("/sessions", json={"client_id": "my_client"})
    session_id = SessionId(response.json()["session_id"])

    populate_session_id(
        client,
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
    session_id: SessionId,
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
    response = client.post("/sessions", json={"client_id": "my_client"})
    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    assert "session_id" in data


def test_that_an_event_can_be_created(
    client: TestClient,
    session_id: SessionId,
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
    session_id: SessionId,
) -> None:
    session_events = [
        make_event_params("client"),
        make_event_params("server"),
        make_event_params("server"),
        make_event_params("client"),
        make_event_params("server"),
    ]

    populate_session_id(client, session_id, session_events)

    response = client.get(f"/sessions/{session_id}/events")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "events" in data

    assert len(data["events"]) == len(session_events)

    for i, event_params, listed_event in zip(count(), session_events, data["events"]):
        assert listed_event["offset"] == i
        assert event_is_according_to_params(event=listed_event, params=event_params)


def test_that_events_can_be_filtered_by_source(
    client: TestClient,
    session_id: SessionId,
) -> None:
    session_events = [
        make_event_params("client"),
        make_event_params("server"),
        make_event_params("client"),
    ]

    populate_session_id(client, session_id, session_events)

    response = client.get(f"/sessions/{session_id}/events", params={"source": "client"})
    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    session_client_events = [e for e in session_events if e["source"] == "client"]

    assert len(data["events"]) == len(session_client_events)

    for event_params, listed_event in zip(session_client_events, data["events"]):
        assert event_is_according_to_params(event=listed_event, params=event_params)


def test_that_a_session_is_created_with_zeroed_out_consumption_offsets(
    client: TestClient,
    long_session_id: SessionId,
) -> None:
    response = client.get(f"/sessions/{long_session_id}")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    assert "consumption_offsets" in data
    assert "server" in data["consumption_offsets"]
    assert "client" in data["consumption_offsets"]
    assert data["consumption_offsets"]["server"] == 0
    assert data["consumption_offsets"]["client"] == 0


@mark.parametrize("consumer_id", ("server", "client"))
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
def test_that_events_can_be_filtered_by_source_and_offset(
    client: TestClient,
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

    populate_session_id(client, session_id, session_events)

    response = client.get(
        f"/sessions/{session_id}/events",
        params={
            "source": "client",
            "min_offset": offset,
        },
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    session_client_events = [e for e in session_events if e["source"] == "client"][
        int(offset / 2) :
    ]

    assert len(data["events"]) == len(session_client_events)

    for event_params, listed_event in zip(session_client_events, data["events"]):
        assert event_is_according_to_params(event=listed_event, params=event_params)
