from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Response, status
from datetime import datetime

from emcie.server.base_models import DefaultBaseModel
from emcie.server.core.agents import AgentId
from emcie.server.core.end_users import EndUserId
from emcie.server.core.sessions import EventId, EventSource, SessionId, SessionStore


class CreateSessionRequest(DefaultBaseModel):
    end_user_id: EndUserId
    agent_id: AgentId


class CreateSessionResponse(DefaultBaseModel):
    session_id: SessionId


class CreateEventRequest(DefaultBaseModel):
    source: EventSource
    type: str
    creation_utc: datetime
    data: Dict[str, Any]


class CreateEventResponse(DefaultBaseModel):
    event_id: EventId


class ConsumptionOffsetsDTO(DefaultBaseModel):
    client: int


class ReadSessionResponse(DefaultBaseModel):
    consumption_offsets: ConsumptionOffsetsDTO


class ConsumptionOffsetsPatchDTO(DefaultBaseModel):
    client: Optional[int] = None


class PatchSessionRequest(DefaultBaseModel):
    consumption_offsets: Optional[ConsumptionOffsetsPatchDTO] = None


class EventDTO(DefaultBaseModel):
    id: EventId
    source: EventSource
    type: str
    offset: int
    creation_utc: datetime
    data: Dict[str, Any]


class ListEventsResponse(DefaultBaseModel):
    events: List[EventDTO]


def create_router(session_store: SessionStore) -> APIRouter:
    router = APIRouter()

    @router.post("/")
    async def create_session(request: CreateSessionRequest) -> CreateSessionResponse:
        session = await session_store.create_session(
            end_user_id=request.end_user_id,
            agent_id=request.agent_id,
        )

        return CreateSessionResponse(session_id=session.id)

    @router.get("/{session_id}")
    async def read_session(session_id: SessionId) -> ReadSessionResponse:
        session = await session_store.read_session(session_id=session_id)

        return ReadSessionResponse(
            consumption_offsets=ConsumptionOffsetsDTO(
                client=session.consumption_offsets["client"],
            )
        )

    @router.patch("/{session_id}")
    async def patch_session(
        session_id: SessionId,
        request: PatchSessionRequest,
    ) -> Response:
        if request.consumption_offsets:
            if request.consumption_offsets.client:
                await session_store.update_consumption_offset(
                    session_id=session_id,
                    consumer_id="client",
                    new_offset=request.consumption_offsets.client,
                )

        return Response(content=None, status_code=status.HTTP_204_NO_CONTENT)

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
        min_offset: Optional[int] = None,
    ) -> ListEventsResponse:
        events = await session_store.list_events(
            session_id=session_id,
            source=source,
            min_offset=min_offset,
        )

        return ListEventsResponse(
            events=[
                EventDTO(
                    id=e.id,
                    source=e.source,
                    type=e.type,
                    offset=e.offset,
                    creation_utc=e.creation_utc,
                    data=e.data,
                )
                for e in events
            ],
        )

    return router
