from datetime import datetime
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from typing import List

from emcie.server.threads import (
    MessageId,
    MessageRole,
    ThreadId,
    ThreadStore,
)


class MessageDTO(BaseModel):
    id: MessageId
    role: MessageRole
    content: str
    creation_utc: datetime
    revision: int


def create_router(thread_store: ThreadStore) -> APIRouter:
    router = APIRouter()

    class CreateThreadResponse(BaseModel):
        thread_id: ThreadId

    @router.post("/")
    async def create_thread() -> CreateThreadResponse:
        thread = await thread_store.create_thread()

        return CreateThreadResponse(
            thread_id=thread.id,
        )

    class CreateMessageRequest(BaseModel):
        role: MessageRole
        content: str

    class CreateMessageResponse(BaseModel):
        message: MessageDTO

    @router.post("/{thread_id}/messages")
    async def create_message(
        thread_id: ThreadId,
        request: CreateMessageRequest,
    ) -> CreateMessageResponse:
        message = await thread_store.create_message(
            thread_id=thread_id,
            role=request.role,
            content=request.content,
        )

        return CreateMessageResponse(
            message=MessageDTO(
                id=message.id,
                role=message.role,
                content=message.content,
                creation_utc=message.creation_utc,
                revision=message.revision,
            )
        )

    class PatchMessageRequest(BaseModel):
        target_revision: int
        content_delta: str

    class PatchMessageResponse(BaseModel):
        patched_message: MessageDTO

    @router.patch("/{thread_id}/messages/{message_id}")
    async def patch_message(
        thread_id: ThreadId,
        message_id: MessageId,
        request: PatchMessageRequest,
    ) -> PatchMessageResponse:
        try:
            patched_message = await thread_store.patch_message(
                thread_id=thread_id,
                message_id=message_id,
                target_revision=request.target_revision,
                content_delta=request.content_delta,
            )

            return PatchMessageResponse(
                patched_message=MessageDTO(
                    id=patched_message.id,
                    role=patched_message.role,
                    content=patched_message.content,
                    creation_utc=patched_message.creation_utc,
                    revision=patched_message.revision,
                )
            )
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(e),
            )

    class ListMessagesResponse(BaseModel):
        messages: List[MessageDTO]

    @router.get("/{thread_id}/messages")
    async def list_messages(
        thread_id: ThreadId,
    ) -> ListMessagesResponse:
        messages = await thread_store.list_messages(thread_id)

        return ListMessagesResponse(
            messages=[
                MessageDTO(
                    id=m.id,
                    role=m.role,
                    content=m.content,
                    creation_utc=m.creation_utc,
                    revision=m.revision,
                )
                for m in messages
            ]
        )

    return router
