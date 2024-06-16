from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, Literal, NewType, Optional

from emcie.server.core import common


SessionId = NewType("SessionId", str)
EventId = NewType("EventId", str)


EventSource = Literal["client", "server"]


@dataclass(frozen=True)
class Event:
    MESSAGE_TYPE = "<message>"
    TOOL_TYPE = "<tool>"

    id: EventId
    source: EventSource
    type: str
    creation_utc: datetime
    offset: int
    data: Dict[str, Any]


@dataclass(frozen=True)
class Session:
    id: SessionId
    client_id: str
    consumption_offsets: Dict[str, int]


class SessionStore:
    def __init__(
        self,
    ) -> None:
        self._sessions: Dict[SessionId, Session] = {}
        self._events: Dict[SessionId, Dict[EventId, Event]] = {}

    async def create_session(self, client_id: str) -> Session:
        session_id = SessionId(common.generate_id())

        self._sessions[session_id] = Session(
            id=session_id,
            client_id=client_id,
            consumption_offsets={
                "server": 0,
                "client": 0,
            },
        )

        self._events[session_id] = {}
        return self._sessions[session_id]

    async def read_session(self, session_id: SessionId) -> Session:
        return self._sessions[session_id]

    async def update_consumption_offset(
        self,
        session_id: SessionId,
        consumer_id: str,
        new_offset: int,
    ) -> None:
        self._sessions[session_id].consumption_offsets[consumer_id] = new_offset

    async def create_event(
        self,
        session_id: SessionId,
        source: EventSource,
        type: str,
        data: Dict[str, Any],
        creation_utc: Optional[datetime] = None,
    ) -> Event:
        event = Event(
            id=EventId(common.generate_id()),
            source=source,
            type=type,
            offset=len(self._events[session_id]),
            data=data,
            creation_utc=creation_utc or datetime.now(timezone.utc),
        )

        self._events[session_id][event.id] = event

        return event

    async def list_events(
        self,
        session_id: SessionId,
        source: Optional[EventSource] = None,
        min_offset: Optional[int] = None,
    ) -> Iterable[Event]:
        events = list(self._events[session_id].values())

        if source:
            events = [e for e in events if e.source == source]

        if min_offset:
            events = [e for e in events if e.offset >= min_offset]

        return events
