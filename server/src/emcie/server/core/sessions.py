from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable, Literal, NewType, Optional, TypedDict

from emcie.server.async_utils import Timeout
from emcie.server.core import common
from emcie.server.core.common import JSONSerializable
from emcie.server.base_models import DefaultBaseModel
from emcie.server.core.agents import AgentId
from emcie.server.core.end_users import EndUserId
from emcie.server.core.persistence import CollectionDescriptor, DocumentDatabase, FieldFilter
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
    class SessionDocument(DefaultBaseModel):
        id: SessionId
        end_user_id: EndUserId
        agent_id: AgentId
        consumption_offsets: dict[ConsumerId, int]

    class EventDocument(DefaultBaseModel):
        id: EventId
        creation_utc: datetime
        session_id: SessionId
        source: EventSource
        kind: str
        offset: int
        data: dict[str, Any]

    def __init__(self, database: DocumentDatabase):
        self._database = database
        self._session_collection = CollectionDescriptor(
            name="sessions",
            schema=self.SessionDocument,
        )
        self._event_collection = CollectionDescriptor(
            name="events",
            schema=self.EventDocument,
        )

    async def create_session(
        self,
        end_user_id: EndUserId,
        agent_id: AgentId,
    ) -> Session:
        session_document = await self._database.insert_one(
            self._session_collection,
            {
                "id": common.generate_id(),
                "end_user_id": end_user_id,
                "agent_id": agent_id,
                "consumption_offsets": {"client": 0},
            },
        )

        return Session(
            id=session_document["id"],
            end_user_id=end_user_id,
            agent_id=agent_id,
            consumption_offsets=session_document["consumption_offsets"],
        )

    async def read_session(
        self,
        session_id: SessionId,
    ) -> Session:
        filters = {"id": FieldFilter(equal_to=session_id)}
        session_document = await self._database.find_one(self._session_collection, filters)

        return Session(
            id=session_document["id"],
            end_user_id=session_document["end_user_id"],
            agent_id=session_document["agent_id"],
            consumption_offsets=session_document["consumption_offsets"],
        )

    async def update_session(
        self,
        session_id: SessionId,
        updated_session: Session,
    ) -> None:
        filters = {"id": FieldFilter(equal_to=session_id)}
        await self._database.update_one(
            self._session_collection,
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
        creation_utc = creation_utc or datetime.now(timezone.utc)

        event_document = await self._database.insert_one(
            self._event_collection,
            {
                "id": common.generate_id(),
                "session_id": session_id,
                "source": source,
                "kind": kind,
                "offset": len(list(session_events)),
                "creation_utc": creation_utc,
                "data": data,
            },
        )

        return Event(
            id=EventId(event_document["id"]),
            source=source,
            kind=kind,
            offset=event_document["offset"],
            creation_utc=creation_utc,
            data=data,
        )

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

        return (
            Event(
                id=EventId(d["id"]),
                source=d["source"],
                kind=d["kind"],
                offset=d["offset"],
                creation_utc=d["creation_utc"],
                data=d["data"],
            )
            for d in await self._database.find(self._event_collection, filters)
        )


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
