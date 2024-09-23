from typing import cast

from emcie.common.types.common import JSONSerializable
from emcie.server.core.emissions import EmittedEvent, EventEmitter, EventEmitterFactory
from emcie.server.core.sessions import (
    MessageEventData,
    SessionId,
    StatusEventData,
    ToolEventData,
)


class EventBuffer(EventEmitter):
    def __init__(self) -> None:
        self.events: list[EmittedEvent] = []

    async def emit_status_event(
        self,
        correlation_id: str,
        data: StatusEventData,
    ) -> EmittedEvent:
        event = EmittedEvent(
            source="server",
            kind="status",
            correlation_id=correlation_id,
            data=cast(JSONSerializable, data),
        )

        self.events.append(event)

        return event

    async def emit_message_event(
        self,
        correlation_id: str,
        data: MessageEventData,
    ) -> EmittedEvent:
        event = EmittedEvent(
            source="server",
            kind="message",
            correlation_id=correlation_id,
            data=cast(JSONSerializable, data),
        )

        self.events.append(event)

        return event

    async def emit_tool_event(
        self,
        correlation_id: str,
        data: ToolEventData,
    ) -> EmittedEvent:
        event = EmittedEvent(
            source="server",
            kind="tool",
            correlation_id=correlation_id,
            data=cast(JSONSerializable, data),
        )

        self.events.append(event)

        return event


class EventBufferFactory(EventEmitterFactory):
    def create_event_emitter(self, session_id: SessionId) -> EventEmitter:
        _ = session_id
        return EventBuffer()
