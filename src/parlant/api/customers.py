from datetime import datetime
from fastapi import APIRouter, status
from typing import Mapping, Optional, Sequence, TypeAlias

from parlant.api.common import apigen_config
from parlant.core.common import DefaultBaseModel
from parlant.core.customers import CustomerId, CustomerStore
from parlant.core.tags import TagId

API_GROUP = "customers"

CustomerExtra: TypeAlias = Mapping[str, str]


class CustomerCreationParamsDTO(DefaultBaseModel):
    name: str
    extra: Optional[CustomerExtra]


class CustomerDTO(DefaultBaseModel):
    id: CustomerId
    creation_utc: datetime
    name: str
    extra: CustomerExtra
    tags: Sequence[TagId]


class CustomerExtraUpdateParamsDTO(DefaultBaseModel):
    add: Optional[CustomerExtra] = None
    remove: Optional[Sequence[str]] = None


class TagsUpdateParamsDTO(DefaultBaseModel):
    add: Optional[Sequence[TagId]] = None
    remove: Optional[Sequence[TagId]] = None


class CustomerUpdateParamsDTO(DefaultBaseModel):
    name: Optional[str] = None
    extra: Optional[CustomerExtraUpdateParamsDTO] = None
    tags: Optional[TagsUpdateParamsDTO] = None


def create_router(
    customer_store: CustomerStore,
) -> APIRouter:
    router = APIRouter()

    @router.post(
        "/",
        status_code=status.HTTP_201_CREATED,
        operation_id="create_customer",
        **apigen_config(group_name=API_GROUP, method_name="create"),
    )
    async def create_customer(params: CustomerCreationParamsDTO) -> CustomerDTO:
        customer = await customer_store.create_customer(
            name=params.name,
            extra=params.extra if params.extra else {},
        )

        return CustomerDTO(
            id=customer.id,
            creation_utc=customer.creation_utc,
            name=customer.name,
            extra=customer.extra,
            tags=customer.tags,
        )

    @router.get(
        "/{customer_id}",
        operation_id="read_customer",
        **apigen_config(group_name=API_GROUP, method_name="retrieve"),
    )
    async def read_customer(customer_id: CustomerId) -> CustomerDTO:
        customer = await customer_store.read_customer(customer_id=customer_id)

        return CustomerDTO(
            id=customer.id,
            creation_utc=customer.creation_utc,
            name=customer.name,
            extra=customer.extra,
            tags=customer.tags,
        )

    @router.get(
        "/",
        operation_id="list_customers",
        **apigen_config(group_name=API_GROUP, method_name="list"),
    )
    async def list_customers() -> list[CustomerDTO]:
        customers = await customer_store.list_customers()

        return [
            CustomerDTO(
                id=customer.id,
                creation_utc=customer.creation_utc,
                name=customer.name,
                extra=customer.extra,
                tags=customer.tags,
            )
            for customer in customers
        ]

    @router.patch(
        "/{customer_id}",
        operation_id="update_customer",
        status_code=status.HTTP_204_NO_CONTENT,
        **apigen_config(group_name=API_GROUP, method_name="update"),
    )
    async def update_customer(customer_id: CustomerId, params: CustomerUpdateParamsDTO) -> None:
        if params.name:
            _ = await customer_store.update_customer(
                customer_id=customer_id,
                params={"name": params.name},
            )

        if params.extra:
            if params.extra.add:
                await customer_store.add_extra(customer_id, params.extra.add)
            if params.extra.remove:
                await customer_store.remove_extra(customer_id, params.extra.remove)

        if params.tags:
            if params.tags.add:
                for tag_id in params.tags.add:
                    await customer_store.add_tag(customer_id, tag_id)
            if params.tags.remove:
                for tag_id in params.tags.remove:
                    await customer_store.remove_tag(customer_id, tag_id)

    @router.delete(
        "/{customer_id}",
        operation_id="delete_customer",
        status_code=status.HTTP_204_NO_CONTENT,
        **apigen_config(group_name=API_GROUP, method_name="delete"),
    )
    async def delete_customer(customer_id: CustomerId) -> None:
        await customer_store.delete_customer(customer_id=customer_id)

    return router
