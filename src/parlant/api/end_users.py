from datetime import datetime
from fastapi import APIRouter, Response, status
from typing import Mapping, Optional, Sequence, TypeAlias, Union

from parlant.core.common import DefaultBaseModel
from parlant.core.end_users import EndUserId, EndUserStore, EndUserUpdateParams
from parlant.core.tags import TagId


EndUserExtraType: TypeAlias = Mapping[str, Union[str, int, float, bool]]


class CreateEndUserRequest(DefaultBaseModel):
    name: str
    extra: Optional[EndUserExtraType]


class EndUserDTO(DefaultBaseModel):
    id: EndUserId
    creation_utc: datetime
    name: str
    extra: EndUserExtraType
    tags: Sequence[TagId]


class CreateEndUserResponse(DefaultBaseModel):
    end_user: EndUserDTO


class ListEndUsersResponse(DefaultBaseModel):
    end_users: list[EndUserDTO]


class ExtraUpdateDTO(DefaultBaseModel):
    add: Optional[EndUserExtraType] = None
    remove: Optional[Sequence[str]] = None


class TagsUpdateDTO(DefaultBaseModel):
    add: Optional[Sequence[TagId]] = None
    remove: Optional[Sequence[TagId]] = None


class UpdateEndUserRequest(DefaultBaseModel):
    name: Optional[str] = None
    extra: Optional[ExtraUpdateDTO] = None
    tags: Optional[TagsUpdateDTO] = None


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
                tags=end_user.tags,
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
            tags=end_user.tags,
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
                    tags=end_user.tags,
                )
                for end_user in end_users
            ]
        )

    @router.patch(
        "/{end_user_id}",
        operation_id="update_end_user",
    )
    async def update_end_user(end_user_id: EndUserId, request: UpdateEndUserRequest) -> Response:
        if request.name:
            params: EndUserUpdateParams = {}
            params["name"] = request.name

            _ = await end_user_store.update_end_user(
                end_user_id=end_user_id,
                params=params,
            )

        if request.extra:
            if request.extra.add:
                await end_user_store.add_extra(end_user_id, request.extra.add)
            if request.extra.remove:
                await end_user_store.remove_extra(end_user_id, request.extra.remove)

        if request.tags:
            if request.tags.add:
                for tag_id in request.tags.add:
                    await end_user_store.add_tag(end_user_id, tag_id)
            if request.tags.remove:
                for tag_id in request.tags.remove:
                    await end_user_store.remove_tag(end_user_id, tag_id)

        return Response(content=None, status_code=status.HTTP_204_NO_CONTENT)

    return router
