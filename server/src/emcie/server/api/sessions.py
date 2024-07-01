from typing import Any, Dict, List, Optional, Union
from fastapi import APIRouter, Response, status
from datetime import datetime

from pydantic import Field

from emcie.server.async_utils import Timeout
from emcie.server.base_models import DefaultBaseModel
from emcie.server.core.agents import AgentId
from emcie.server.core.end_users import EndUserId
from emcie.server.core.sessions import (
    Event,
    EventId,
    EventSource,
    SessionId,
    SessionListener,
    SessionStore,
)
from emcie.server.mc import MC


class CreateSessionRequest(DefaultBaseModel):
    end_user_id: EndUserId
    agent_id: AgentId


class CreateSessionResponse(DefaultBaseModel):
    session_id: SessionId


class CreateMessageRequest(DefaultBaseModel):
    kind: str = Field(Event.MESSAGE_TYPE, description=f'Internal (leave as "{Event.MESSAGE_TYPE}")')
    content: str


class CreateEventResponse(DefaultBaseModel):
    event_id: EventId
    event_offset: int


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
    kind: str
    offset: int
    creation_utc: datetime
    data: Dict[str, Any]


class ListEventsResponse(DefaultBaseModel):
    events: List[EventDTO]


def create_router(
    mc: MC,
    session_store: SessionStore,
    session_listener: SessionListener,
) -> APIRouter:
    router = APIRouter()

    @router.post("/")
    async def create_session(request: CreateSessionRequest) -> CreateSessionResponse:
        session = await mc.create_end_user_session(
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
                session = await session_store.read_session(session_id)

                await mc.update_consumption_offset(
                    session=session,
                    new_offset=request.consumption_offsets.client,
                )

        return Response(content=None, status_code=status.HTTP_204_NO_CONTENT)

    @router.post("/{session_id}/events")
    async def create_event(
        session_id: SessionId,
        request: Union[CreateMessageRequest],
    ) -> CreateEventResponse:
        event = await mc.post_client_event(
            session_id=session_id,
            kind=request.kind,
            data={"message": request.content},
        )

        return CreateEventResponse(
            event_id=event.id,
            event_offset=event.offset,
        )

    @router.get("/{session_id}/events")
    async def list_events(
        session_id: SessionId,
        min_offset: Optional[int] = None,
        wait: Optional[bool] = None,
    ) -> ListEventsResponse:
        if wait:
            await session_listener.wait_for_events(
                session_id=session_id,
                min_offset=min_offset or 0,
                timeout=Timeout(60),
            )

        events = await session_store.list_events(
            session_id=session_id,
            source=None,
            min_offset=min_offset,
        )

        return ListEventsResponse(
            events=[
                EventDTO(
                    id=e.id,
                    source=e.source,
                    kind=e.kind,
                    offset=e.offset,
                    creation_utc=e.creation_utc,
                    data=e.data,
                )
                for e in events
            ],
        )

    return router
