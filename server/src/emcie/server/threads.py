from typing import Dict, Iterable, List, Literal, NewType, Optional
from datetime import datetime

from emcie.server import common


MessageId = NewType("MessageId", str)
ThreadId = NewType("ThreadId", str)


MessageRole = Literal["user"]


class Message:
    def __init__(
        self,
        id: MessageId,
        role: MessageRole,
        content: str,
        creation_utc: datetime,
    ) -> None:
        self.id = id
        self.role = role
        self.content = content
        self.creation_utc = creation_utc


class Thread:
    def __init__(
        self,
        id: ThreadId,
    ) -> None:
        self.id = id


class ThreadStore:
    def __init__(
        self,
    ) -> None:
        self._threads: Dict[ThreadId, Thread] = {}
        self._messages: Dict[ThreadId, List[Message]] = {}

    async def create_thread(self) -> ThreadId:
        thread_id = ThreadId(common.generate_id())
        self._threads[thread_id] = Thread(thread_id)
        self._messages[thread_id] = []
        return thread_id

    async def create_message(
        self,
        thread_id: ThreadId,
        role: MessageRole,
        content: str,
        creation_utc: Optional[datetime] = None,
    ) -> MessageId:
        message_id = MessageId(common.generate_id())

        self._messages[thread_id].append(
            Message(
                id=message_id,
                role=role,
                content=content,
                creation_utc=creation_utc or datetime.utcnow(),
            )
        )

        return message_id

    async def list_messages(self, thread_id: ThreadId) -> Iterable[Message]:
        return self._messages[thread_id]
