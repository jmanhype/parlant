from typing import Any, Dict, List, Optional
from fastapi import APIRouter
from pydantic import BaseModel
from datetime import datetime

from emcie.server.sessions import EventId, EventSource, SessionId, SessionStore


class CreateSessionResponse(BaseModel):
    session_id: SessionId


class CreateEventRequest(BaseModel):
    source: EventSource
    type: str
    creation_utc: datetime
    data: Dict[str, Any]


class CreateEventResponse(BaseModel):
    event_id: EventId


class EventDTO(BaseModel):
    id: EventId
    source: EventSource
    type: str
    creation_utc: datetime
    data: Dict[str, Any]


class ListEventsResponse(BaseModel):
    events: List[EventDTO]


def create_router(session_store: SessionStore) -> APIRouter:
    router = APIRouter()

    @router.post("/")
    async def create_session() -> CreateSessionResponse:
        session = await session_store.create_session()
        return CreateSessionResponse(session_id=session.id)

    @router.post("/{session_id}/events")
    async def create_event(
        session_id: SessionId,
        request: CreateEventRequest,
    ) -> CreateEventResponse:
        event = await session_store.create_event(
            session_id=session_id,
            source=request.source,
            type=request.type,
            data=request.data,
            creation_utc=request.creation_utc,
        )

        return CreateEventResponse(event_id=event.id)

    @router.get("/{session_id}/events")
    async def list_events(
        session_id: SessionId,
        source: Optional[EventSource] = None,
    ) -> ListEventsResponse:
        events = await session_store.list_events(
            session_id=session_id,
            source=source,
        )

        return ListEventsResponse(
            events=[
                EventDTO(
                    id=e.id, source=e.source, type=e.type, creation_utc=e.creation_utc, data=e.data
                )
                for e in events
            ]
        )

    return router
