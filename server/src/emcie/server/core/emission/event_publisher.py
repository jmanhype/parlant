from typing import cast

from emcie.common.types.common import JSONSerializable
from emcie.server.core.emissions import EmittedEvent, EventEmitter
from emcie.server.core.sessions import (
    MessageEventData,
    SessionId,
    SessionStore,
    StatusEventData,
    ToolEventData,
)


class EventPublisher(EventEmitter):
    def __init__(
        self,
        session_store: SessionStore,
        session_id: SessionId,
    ) -> None:
        self._store = session_store
        self._session_id = session_id

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

        await self._publish_event(event)

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

        await self._publish_event(event)

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

        await self._publish_event(event)

        return event

    async def _publish_event(
        self,
        event: EmittedEvent,
    ) -> None:
        await self._store.create_event(
            session_id=self._session_id,
            source="server",
            kind=event.kind,
            correlation_id=event.correlation_id,
            data=event.data,
        )
