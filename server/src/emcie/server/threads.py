from dataclasses import dataclass
from typing import Dict, Iterable, Literal, NewType, Optional
from datetime import datetime, timezone

from emcie.server import common


MessageId = NewType("MessageId", str)
ThreadId = NewType("ThreadId", str)


MessageRole = Literal["user", "assistant"]


@dataclass(frozen=True)
class Message:
    id: MessageId
    role: MessageRole
    content: str
    completed: bool
    creation_utc: datetime
    revision: int = 0


@dataclass(frozen=True)
class Thread:
    id: ThreadId


class ThreadStore:
    def __init__(
        self,
    ) -> None:
        self._threads: Dict[ThreadId, Thread] = {}
        self._messages: Dict[ThreadId, Dict[MessageId, Message]] = {}

    async def create_thread(self) -> Thread:
        thread_id = ThreadId(common.generate_id())
        self._threads[thread_id] = Thread(thread_id)
        self._messages[thread_id] = {}
        return self._threads[thread_id]

    async def create_message(
        self,
        thread_id: ThreadId,
        role: MessageRole,
        content: str,
        completed: bool,
        creation_utc: Optional[datetime] = None,
    ) -> Message:
        message = Message(
            id=MessageId(common.generate_id()),
            role=role,
            content=content,
            completed=completed,
            creation_utc=creation_utc or datetime.now(timezone.utc),
        )

        self._messages[thread_id][message.id] = message

        return message

    async def patch_message(
        self,
        thread_id: ThreadId,
        message_id: MessageId,
        target_revision: int,
        content_delta: str,
        completed: bool,
    ) -> Message:
        message = self._messages[thread_id][message_id]

        if message.revision != target_revision:
            raise ValueError("Target revision is not the current one")

        self._messages[thread_id][message_id] = Message(
            id=message.id,
            role=message.role,
            content=(message.content + content_delta),
            completed=completed,
            creation_utc=message.creation_utc,
            revision=(message.revision + 1),
        )

        return message

    async def list_messages(self, thread_id: ThreadId) -> Iterable[Message]:
        return self._messages[thread_id].values()

    async def read_message(
        self,
        thread_id: ThreadId,
        message_id: MessageId,
    ) -> Message:
        return self._messages[thread_id][message_id]
