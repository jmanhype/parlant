from typing import List, Literal
from fastapi import APIRouter
from pydantic import BaseModel
from datetime import datetime

from emcie.server.threads import ThreadId, ThreadStore


def create_router(thread_store: ThreadStore) -> APIRouter:
    router = APIRouter()

    class MessageDTO(BaseModel):
        role: Literal["user"]
        content: str
        creation_utc: datetime

    class CreateThreadResponse(BaseModel):
        thread_id: str

    @router.post("/")
    async def create_thread() -> CreateThreadResponse:
        thread_id = await thread_store.create_thread()

        return CreateThreadResponse(
            thread_id=thread_id,
        )

    class CreateMessageRequest(BaseModel):
        role: Literal["user"]
        content: str

    class CreateMessageResponse(BaseModel):
        pass

    @router.post("/{thread_id}/messages")
    async def create_message(
        thread_id: str,
        request: CreateMessageRequest,
    ) -> CreateMessageResponse:
        await thread_store.create_message(
            thread_id=ThreadId(thread_id),
            role=request.role,
            content=request.content,
        )

        return CreateMessageResponse()

    class ListMessagesResponse(BaseModel):
        messages: List[MessageDTO]

    @router.get("/{thread_id}/messages")
    async def list_messages(
        thread_id: str,
    ) -> ListMessagesResponse:
        messages = await thread_store.list_messages(ThreadId(thread_id))

        return ListMessagesResponse(
            messages=[
                MessageDTO(
                    role=m.role,
                    content=m.content,
                    creation_utc=m.creation_utc,
                )
                for m in messages
            ]
        )

    return router
