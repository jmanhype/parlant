from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, Literal, NewType, Optional, TypedDict

from emcie.server.async_utils import Timeout
from emcie.server.core.common import JSONSerializable, create_instance_from_dict
from emcie.server.core.agents import AgentId
from emcie.server.core.end_users import EndUserId
from emcie.server.core.persistence import DocumentDatabase, FieldFilter
from emcie.server.core.tools import ToolParameter

SessionId = NewType("SessionId", str)
EventId = NewType("EventId", str)


EventSource = Literal["client", "server"]


@dataclass(frozen=True)
class Event:
    MESSAGE_KIND = "<message>"
    TOOL_KIND = "<tool>"

    id: EventId
    source: EventSource
    kind: str
    creation_utc: datetime
    offset: int
    data: JSONSerializable


class MessageEventData(TypedDict):
    message: str


class _ToolResult(TypedDict):
    tool_name: str
    parameters: dict[str, ToolParameter]
    result: JSONSerializable


class ToolEventData(TypedDict):
    tool_results: list[_ToolResult]


ConsumerId = Literal["client"]
"""In the future we may support multiple consumer IDs"""


@dataclass(frozen=True)
class Session:
    id: SessionId
    end_user_id: EndUserId
    agent_id: AgentId
    consumption_offsets: dict[ConsumerId, int]


class SessionStore(ABC):
    @abstractmethod
    async def create_session(
        self,
        end_user_id: EndUserId,
        agent_id: AgentId,
    ) -> Session: ...

    @abstractmethod
    async def read_session(
        self,
        session_id: SessionId,
    ) -> Session: ...

    @abstractmethod
    async def update_consumption_offset(
        self,
        session_id: SessionId,
        consumer_id: ConsumerId,
        new_offset: int,
    ) -> None: ...

    @abstractmethod
    async def create_event(
        self,
        session_id: SessionId,
        source: EventSource,
        kind: str,
        data: JSONSerializable,
        creation_utc: Optional[datetime] = None,
    ) -> Event: ...

    @abstractmethod
    async def list_events(
        self,
        session_id: SessionId,
        source: Optional[EventSource] = None,
        min_offset: Optional[int] = None,
    ) -> Iterable[Event]: ...


class SessionDocumentStore(SessionStore):
    def __init__(self, database: DocumentDatabase):
        self._database = database
        self._session_collection_name = "sessions"
        self._event_collection_name = "events"

    async def create_session(
        self,
        end_user_id: EndUserId,
        agent_id: AgentId,
    ) -> Session:
        session_data = {
            "end_user_id": end_user_id,
            "agent_id": agent_id,
            "consumption_offsets": {"client": 0},
        }
        inserted_session = await self._database.insert_one(
            self._session_collection_name, session_data
        )
        return create_instance_from_dict(Session, inserted_session)

    async def read_session(
        self,
        session_id: SessionId,
    ) -> Session:
        filters = {"id": FieldFilter(equal_to=session_id)}
        found_session = await self._database.find_one(self._session_collection_name, filters)
        return create_instance_from_dict(Session, found_session)

    async def update_session(
        self,
        session_id: SessionId,
        updated_session: Session,
    ) -> None:
        filters = {"id": FieldFilter(equal_to=session_id)}
        await self._database.update_one(
            self._session_collection_name,
            filters,
            updated_session.__dict__,
        )

    async def update_consumption_offset(
        self,
        session_id: SessionId,
        consumer_id: ConsumerId,
        new_offset: int,
    ) -> None:
        session = await self.read_session(session_id)
        session.consumption_offsets[consumer_id] = new_offset
        await self.update_session(session_id, session)

    async def create_event(
        self,
        session_id: SessionId,
        source: EventSource,
        kind: str,
        data: JSONSerializable,
        creation_utc: Optional[datetime] = None,
    ) -> Event:
        session_events = await self.list_events(session_id)
        event_data = {
            "session_id": session_id,
            "source": source,
            "kind": kind,
            "offset": len(list(session_events)),
            "creation_utc": creation_utc or datetime.now(timezone.utc),
            "data": data,
        }
        inserted_event = await self._database.insert_one(self._event_collection_name, event_data)
        return create_instance_from_dict(Event, inserted_event)

    async def list_events(
        self,
        session_id: SessionId,
        source: Optional[EventSource] = None,
        min_offset: Optional[int] = None,
    ) -> Iterable[Event]:
        source_filter = {"source": FieldFilter(equal_to=source)} if source else {}
        offset_filter = (
            {"offset": FieldFilter(greater_than_or_equal_to=min_offset)} if min_offset else {}
        )
        filters = {
            **{"session_id": FieldFilter(equal_to=session_id)},
            **source_filter,
            **offset_filter,
        }
        found_events = await self._database.find(self._event_collection_name, filters)
        return (create_instance_from_dict(Event, event) for event in found_events)


class SessionListener(ABC):
    @abstractmethod
    async def wait_for_events(
        self,
        session_id: SessionId,
        min_offset: int,
        timeout: Timeout,
    ) -> bool: ...


class PollingSessionListener(SessionListener):
    def __init__(self, session_store: SessionStore) -> None:
        self._session_store = session_store

    async def wait_for_events(
        self,
        session_id: SessionId,
        min_offset: int,
        timeout: Timeout,
        # TODO: allow filtering based on type (e.g. to filter out tool events)
    ) -> bool:
        while True:
            events = list(
                await self._session_store.list_events(
                    session_id,
                    source="server",
                    min_offset=min_offset,
                )
            )

            if events:
                return True
            elif timeout.expired():
                return False
            else:
                await timeout.wait_up_to(1)
