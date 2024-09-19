from datetime import datetime
from itertools import chain, groupby
from typing import Any, Literal, Mapping, Optional, Union, cast

from fastapi import APIRouter, HTTPException, Query, Response, status
from pydantic import Field

from emcie.server.core.async_utils import Timeout
from emcie.server.core.common import DefaultBaseModel
from emcie.server.core.agents import AgentId
from emcie.server.core.end_users import EndUserId
from emcie.server.core.sessions import (
    EventId,
    EventKind,
    EventSource,
    MessageEventData,
    SessionId,
    SessionListener,
    SessionStore,
    ToolEventData,
)
from emcie.server.core.mc import MC


class CreateSessionRequest(DefaultBaseModel):
    end_user_id: EndUserId
    agent_id: AgentId
    title: Optional[str] = None


class CreateSessionResponse(DefaultBaseModel):
    session_id: SessionId
    creation_utc: datetime
    title: Optional[str] = None


class CreateMessageRequest(DefaultBaseModel):
    kind: EventKind = Field("message", description='Internal (leave as "message")')
    content: str


class CreateEventResponse(DefaultBaseModel):
    event_id: EventId
    event_offset: int


class ConsumptionOffsetsDTO(DefaultBaseModel):
    client: int


class SessionDTO(DefaultBaseModel):
    session_id: SessionId
    end_user_id: EndUserId
    creation_utc: datetime
    consumption_offsets: ConsumptionOffsetsDTO
    title: Optional[str] = None


class ConsumptionOffsetsPatchDTO(DefaultBaseModel):
    client: Optional[int] = None


class PatchSessionRequest(DefaultBaseModel):
    consumption_offsets: Optional[ConsumptionOffsetsPatchDTO] = None
    title: Optional[str] = None


class EventDTO(DefaultBaseModel):
    id: EventId
    source: EventSource
    kind: str
    offset: int
    creation_utc: datetime
    correlation_id: str
    data: Any


class ListEventsResponse(DefaultBaseModel):
    session_id: SessionId
    events: list[EventDTO]


class ListSessionsResponse(DefaultBaseModel):
    sessions: list[SessionDTO]


class DeleteSessionResponse(DefaultBaseModel):
    session_id: SessionId


class ToolResultDTO(DefaultBaseModel):
    data: Any
    metadata: Mapping[str, Any]


class ToolCallDTO(DefaultBaseModel):
    tool_name: str
    arguments: Mapping[str, Any]
    result: ToolResultDTO


class InteractionDTO(DefaultBaseModel):
    kind: Literal["message"]
    source: EventSource
    correlation_id: str
    data: Any = Field(
        description="The data associated with this interaction's kind. "
        "If kind is 'message', this is the message string."
    )
    tool_calls: list[ToolCallDTO]


class ListInteractionsResponse(DefaultBaseModel):
    session_id: SessionId
    interactions: list[InteractionDTO]


def create_router(
    mc: MC,
    session_store: SessionStore,
    session_listener: SessionListener,
) -> APIRouter:
    router = APIRouter()

    @router.post("/", status_code=status.HTTP_201_CREATED)
    async def create_session(
        request: CreateSessionRequest,
        allow_greeting: bool = Query(default=True),
    ) -> CreateSessionResponse:
        session = await mc.create_end_user_session(
            end_user_id=request.end_user_id,
            agent_id=request.agent_id,
            title=request.title,
            allow_greeting=allow_greeting,
        )

        return CreateSessionResponse(
            session_id=session.id, title=session.title, creation_utc=session.creation_utc
        )

    @router.get("/{session_id}")
    async def read_session(session_id: SessionId) -> SessionDTO:
        session = await session_store.read_session(session_id=session_id)

        return SessionDTO(
            session_id=session.id,
            creation_utc=session.creation_utc,
            title=session.title,
            end_user_id=session.end_user_id,
            consumption_offsets=ConsumptionOffsetsDTO(
                client=session.consumption_offsets["client"],
            ),
        )

    @router.get("/")
    async def list_sessions(agent_id: Optional[AgentId] = None) -> ListSessionsResponse:
        sessions = await session_store.list_sessions(agent_id=agent_id)

        return ListSessionsResponse(
            sessions=[
                SessionDTO(
                    session_id=s.id,
                    creation_utc=s.creation_utc,
                    title=s.title,
                    end_user_id=s.end_user_id,
                    consumption_offsets=ConsumptionOffsetsDTO(
                        client=s.consumption_offsets["client"],
                    ),
                )
                for s in sessions
            ]
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
        if request.title:
            await session_store.update_title(session_id=session_id, title=request.title)

        return Response(content=None, status_code=status.HTTP_204_NO_CONTENT)

    @router.delete("/{session_id}")
    async def delete_session(
        session_id: SessionId,
    ) -> DeleteSessionResponse:
        if await session_store.delete_session(session_id):
            return DeleteSessionResponse(session_id=session_id)
        else:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    @router.post("/{session_id}/events", status_code=status.HTTP_201_CREATED)
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
            if not await session_listener.wait_for_events(
                session_id=session_id,
                min_offset=min_offset or 0,
                kinds=[],
                timeout=Timeout(60),
            ):
                raise HTTPException(
                    status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                    detail="Request timed out",
                )

        events = await session_store.list_events(
            session_id=session_id,
            source=None,
            min_offset=min_offset,
        )

        return ListEventsResponse(
            session_id=session_id,
            events=[
                EventDTO(
                    id=e.id,
                    source=e.source,
                    kind=e.kind,
                    offset=e.offset,
                    creation_utc=e.creation_utc,
                    correlation_id=e.correlation_id,
                    data=e.data,
                )
                for e in events
            ],
        )

    @router.get("/{session_id}/interactions")
    async def list_interactions(
        session_id: SessionId,
        min_event_offset: int,
        source: EventSource,
        wait: bool = False,
    ) -> ListInteractionsResponse:
        if wait:
            await mc.wait_for_update(
                session_id=session_id,
                min_offset=min_event_offset,
                kinds=["message"],
                source=source,
                timeout=Timeout(300),
            )

        events = await session_store.list_events(
            session_id=session_id,
            kinds=["message", "tool"],
            source=source,
            min_offset=min_event_offset,
        )

        interactions = []

        for correlation_id, correlated_events in groupby(events, key=lambda e: e.correlation_id):
            message_events = [e for e in correlated_events if e.kind == "message"]
            tool_events = [e for e in correlated_events if e.kind == "tool"]

            tool_calls = list(
                chain.from_iterable(cast(ToolEventData, e.data)["tool_calls"] for e in tool_events)
            )

            for e in message_events:
                interactions.append(
                    InteractionDTO(
                        kind="message",
                        source=e.source,
                        correlation_id=correlation_id,
                        data=cast(MessageEventData, e.data)["message"],
                        tool_calls=[
                            ToolCallDTO(
                                tool_name=tc["tool_name"],
                                arguments=tc["arguments"],
                                result=ToolResultDTO(
                                    data=tc["result"]["data"],
                                    metadata=tc["result"]["metadata"],
                                ),
                            )
                            for tc in tool_calls
                        ],
                    )
                )

        return ListInteractionsResponse(
            session_id=session_id,
            interactions=interactions,
        )

    return router
