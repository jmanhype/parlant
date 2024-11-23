from datetime import datetime
from fastapi import APIRouter, status

from parlant.api.common import apigen_config
from parlant.core.common import DefaultBaseModel
from parlant.core.tags import TagId, TagStore, TagUpdateParams

API_GROUP = "tags"


class TagDTO(DefaultBaseModel):
    id: TagId
    creation_utc: datetime
    name: str


class TagCreationParamsDTO(DefaultBaseModel):
    name: str


class TagUpdateParamsDTO(DefaultBaseModel):
    name: str


def create_router(
    tag_store: TagStore,
) -> APIRouter:
    router = APIRouter()

    @router.post(
        "/",
        status_code=status.HTTP_201_CREATED,
        operation_id="create_tag",
        **apigen_config(group_name=API_GROUP, method_name="create"),
    )
    async def create_tag(request: TagCreationParamsDTO) -> TagDTO:
        tag = await tag_store.create_tag(
            name=request.name,
        )

        return TagDTO(id=tag.id, creation_utc=tag.creation_utc, name=tag.name)

    @router.get(
        "/{tag_id}",
        operation_id="read_tag",
        **apigen_config(group_name=API_GROUP, method_name="retrieve"),
    )
    async def read_tag(tag_id: TagId) -> TagDTO:
        tag = await tag_store.read_tag(tag_id=tag_id)

        return TagDTO(id=tag.id, creation_utc=tag.creation_utc, name=tag.name)

    @router.get(
        "/",
        operation_id="list_tags",
        **apigen_config(group_name=API_GROUP, method_name="list"),
    )
    async def list_tags() -> list[TagDTO]:
        tags = await tag_store.list_tags()

        return [TagDTO(id=tag.id, creation_utc=tag.creation_utc, name=tag.name) for tag in tags]

    @router.patch(
        "/{tag_id}",
        operation_id="update_tag",
        status_code=status.HTTP_204_NO_CONTENT,
        **apigen_config(group_name=API_GROUP, method_name="update"),
    )
    async def update_tag(tag_id: TagId, request: TagUpdateParamsDTO) -> None:
        params: TagUpdateParams = {"name": request.name}

        await tag_store.update_tag(
            tag_id=tag_id,
            params=params,
        )

    @router.delete(
        "/{tag_id}",
        status_code=status.HTTP_204_NO_CONTENT,
        operation_id="delete_tag",
        **apigen_config(group_name=API_GROUP, method_name="delete"),
    )
    async def delete_tag(tag_id: TagId) -> None:
        await tag_store.delete_tag(tag_id=tag_id)

    return router
