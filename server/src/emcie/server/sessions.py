from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, Literal, NewType, Optional

from emcie.server import common


SessionId = NewType("SessionId", str)
EventId = NewType("EventId", str)


EventSource = Literal["client", "server"]


@dataclass(frozen=True)
class Event:
    id: EventId
    source: EventSource
    type: str
    creation_utc: datetime
    data: Dict[str, Any]


@dataclass(frozen=True)
class Session:
    id: SessionId


class SessionStore:
    def __init__(
        self,
    ) -> None:
        self._sessions: Dict[SessionId, Session] = {}
        self._events: Dict[SessionId, Dict[EventId, Event]] = {}

    async def create_session(self) -> Session:
        session_id = SessionId(common.generate_id())
        self._sessions[session_id] = Session(session_id)
        self._events[session_id] = {}
        return self._sessions[session_id]

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
            data=data,
            creation_utc=creation_utc or datetime.now(timezone.utc),
        )

        self._events[session_id][event.id] = event

        return event

    async def list_events(
        self,
        session_id: SessionId,
        source: Optional[EventSource] = None,
    ) -> Iterable[Event]:
        events = list(self._events[session_id].values())

        if source:
            events = [e for e in events if e.source == source]

        return events
