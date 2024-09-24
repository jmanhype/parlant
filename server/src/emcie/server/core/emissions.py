from abc import ABC, abstractmethod
from dataclasses import dataclass

from emcie.server.core.common import JSONSerializable
from emcie.server.core.sessions import (
    EventKind,
    EventSource,
    MessageEventData,
    SessionId,
    StatusEventData,
    ToolEventData,
)


@dataclass(frozen=True)
class EmittedEvent:
    source: EventSource
    kind: EventKind
    correlation_id: str
    data: JSONSerializable


class EventEmitter(ABC):
    @abstractmethod
    async def emit_status_event(
        self,
        correlation_id: str,
        data: StatusEventData,
    ) -> EmittedEvent: ...

    @abstractmethod
    async def emit_message_event(
        self,
        correlation_id: str,
        data: MessageEventData,
    ) -> EmittedEvent: ...

    @abstractmethod
    async def emit_tool_event(
        self,
        correlation_id: str,
        data: ToolEventData,
    ) -> EmittedEvent: ...


class EventEmitterFactory(ABC):
    @abstractmethod
    def create_event_emitter(
        self,
        session_id: SessionId,
    ) -> EventEmitter: ...
