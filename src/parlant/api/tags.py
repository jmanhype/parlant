from datetime import datetime
from fastapi import APIRouter, Response, status

from parlant.core.common import DefaultBaseModel
from parlant.core.tags import TagId, TagStore, TagUpdateParams


class TagDTO(DefaultBaseModel):
    id: TagId
    creation_utc: datetime
    name: str


class CreateTagRequest(DefaultBaseModel):
    name: str


class CreateTagResponse(DefaultBaseModel):
    tag: TagDTO


class ListTagsResponse(DefaultBaseModel):
    tags: list[TagDTO]


class DeleteTagResponse(DefaultBaseModel):
    tag_id: TagId


class UpdateTagRequest(DefaultBaseModel):
    name: str


def create_router(
    tag_store: TagStore,
) -> APIRouter:
    router = APIRouter()

    @router.post(
        "/",
        status_code=status.HTTP_201_CREATED,
        operation_id="create_tag",
    )
    async def create_tag(request: CreateTagRequest) -> CreateTagResponse:
        tag = await tag_store.create_tag(
            name=request.name,
        )

        return CreateTagResponse(
            tag=TagDTO(id=tag.id, creation_utc=tag.creation_utc, name=tag.name)
        )

    @router.get(
        "/{tag_id}",
        operation_id="read_tag",
    )
    async def read_tag(tag_id: TagId) -> TagDTO:
        tag = await tag_store.read_tag(tag_id=tag_id)

        return TagDTO(id=tag.id, creation_utc=tag.creation_utc, name=tag.name)

    @router.get(
        "/",
        operation_id="list_tags",
    )
    async def list_tags() -> ListTagsResponse:
        tags = await tag_store.list_tags()

        return ListTagsResponse(
            tags=[TagDTO(id=tag.id, creation_utc=tag.creation_utc, name=tag.name) for tag in tags]
        )

    @router.patch(
        "/{tag_id}",
        operation_id="update_tag",
    )
    async def update_tag(tag_id: TagId, request: UpdateTagRequest) -> Response:
        params: TagUpdateParams = {"name": request.name}

        await tag_store.update_tag(
            tag_id=tag_id,
            params=params,
        )

        return Response(content=None, status_code=status.HTTP_204_NO_CONTENT)

    @router.delete(
        "/{tag_id}",
        operation_id="delete_tag",
    )
    async def delete_tag(tag_id: TagId) -> DeleteTagResponse:
        await tag_store.delete_tag(tag_id=tag_id)
        return DeleteTagResponse(tag_id=tag_id)

    return router
