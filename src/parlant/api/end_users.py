from datetime import datetime
from fastapi import APIRouter, status
from typing import Mapping, Optional, Union

from parlant.core.common import DefaultBaseModel
from parlant.core.end_users import EndUserId, EndUserStore, EndUserTagId, EndUserUpdateParams


class CreateEndUserRequest(DefaultBaseModel):
    name: str
    extra: Optional[Mapping[str, Union[str, int, float, bool]]]


class EndUserDTO(DefaultBaseModel):
    id: EndUserId
    creation_utc: datetime
    name: str
    extra: Mapping[str, Union[str, int, float, bool]]


class CreateEndUserResponse(DefaultBaseModel):
    end_user: EndUserDTO


class ListEndUsersResponse(DefaultBaseModel):
    end_users: list[EndUserDTO]


class PatchEndUserRequest(DefaultBaseModel):
    name: Optional[str] = None
    extra: Optional[Mapping[str, Union[str, int, float, bool]]] = None


class EndUserTag(DefaultBaseModel):
    id: EndUserTagId
    creation_utc: datetime
    label: str


class CreateTagRequest(DefaultBaseModel):
    label: str


class CreateTagResponse(DefaultBaseModel):
    tag: EndUserTag


class ListTagsResponse(DefaultBaseModel):
    tags: list[EndUserTag]


class DeleteTagResponse(DefaultBaseModel):
    tag_id: EndUserTagId


def create_router(
    end_user_store: EndUserStore,
) -> APIRouter:
    router = APIRouter()

    @router.post(
        "/",
        status_code=status.HTTP_201_CREATED,
        operation_id="create_end_user",
    )
    async def create_end_user(request: CreateEndUserRequest) -> CreateEndUserResponse:
        end_user = await end_user_store.create_end_user(
            name=request.name,
            extra=request.extra if request.extra else {},
        )

        return CreateEndUserResponse(
            end_user=EndUserDTO(
                id=end_user.id,
                creation_utc=end_user.creation_utc,
                name=end_user.name,
                extra=end_user.extra,
            )
        )

    @router.get(
        "/{end_user_id}",
        operation_id="read_end_user",
    )
    async def read_end_user(end_user_id: EndUserId) -> EndUserDTO:
        end_user = await end_user_store.read_end_user(end_user_id=end_user_id)

        return EndUserDTO(
            id=end_user.id,
            creation_utc=end_user.creation_utc,
            name=end_user.name,
            extra=end_user.extra,
        )

    @router.get(
        "/",
        operation_id="list_end_users",
    )
    async def list_end_users() -> ListEndUsersResponse:
        end_users = await end_user_store.list_end_users()

        return ListEndUsersResponse(
            end_users=[
                EndUserDTO(
                    id=end_user.id,
                    creation_utc=end_user.creation_utc,
                    name=end_user.name,
                    extra=end_user.extra,
                )
                for end_user in end_users
            ]
        )

    @router.patch(
        "/{end_user_id}",
        operation_id="patch_end_user",
    )
    async def patch_end_user(end_user_id: EndUserId, request: PatchEndUserRequest) -> EndUserDTO:
        params: EndUserUpdateParams = {}
        if request.name:
            params["name"] = request.name
        if request.extra:
            params["extra"] = request.extra

        end_user = await end_user_store.update_end_user(
            end_user_id=end_user_id,
            params=params,
        )

        return EndUserDTO(
            id=end_user.id,
            creation_utc=end_user.creation_utc,
            name=end_user.name,
            extra=end_user.extra,
        )

    @router.post(
        "/{end_user_id}/tags",
        status_code=status.HTTP_201_CREATED,
        operation_id="create_tag",
    )
    async def create_tag(end_user_id: EndUserId, request: CreateTagRequest) -> EndUserTag:
        tag = await end_user_store.set_tag(end_user_id=end_user_id, label=request.label)
        return EndUserTag(id=tag.id, creation_utc=tag.creation_utc, label=tag.label)

    @router.get(
        "/{end_user_id}/tags",
        operation_id="list_tags",
    )
    async def list_tags(end_user_id: EndUserId) -> ListTagsResponse:
        tags = await end_user_store.get_tags(end_user_id=end_user_id)
        return ListTagsResponse(
            tags=[
                EndUserTag(id=tag.id, creation_utc=tag.creation_utc, label=tag.label)
                for tag in tags
            ]
        )

    @router.delete(
        "/{end_user_id}/tags/{tag_id}",
        operation_id="delete_tag",
    )
    async def delete_tag(end_user_id: EndUserId, tag_id: EndUserTagId) -> DeleteTagResponse:
        await end_user_store.delete_tag(end_user_id=end_user_id, tag_id=tag_id)
        return DeleteTagResponse(tag_id=tag_id)

    return router
