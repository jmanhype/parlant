from datetime import datetime
from fastapi import APIRouter, status
from typing import Mapping, Optional, Sequence, TypeAlias

from parlant.api.common import apigen_config
from parlant.core.common import DefaultBaseModel
from parlant.core.customers import CustomerId, CustomerStore, CustomerUpdateParams
from parlant.core.tags import TagId

API_GROUP = "customers"

CustomerExtraType: TypeAlias = Mapping[str, str]


class CreateCustomerRequest(DefaultBaseModel):
    name: str
    extra: Optional[CustomerExtraType]


class CustomerDTO(DefaultBaseModel):
    id: CustomerId
    creation_utc: datetime
    name: str
    extra: CustomerExtraType
    tags: Sequence[TagId]


class CreateCustomerResult(DefaultBaseModel):
    customer: CustomerDTO


class ListCustomersResult(DefaultBaseModel):
    customers: list[CustomerDTO]


class ExtraUpdateDTO(DefaultBaseModel):
    add: Optional[CustomerExtraType] = None
    remove: Optional[Sequence[str]] = None


class TagsUpdateDTO(DefaultBaseModel):
    add: Optional[Sequence[TagId]] = None
    remove: Optional[Sequence[TagId]] = None


class UpdateCustomerRequest(DefaultBaseModel):
    name: Optional[str] = None
    extra: Optional[ExtraUpdateDTO] = None
    tags: Optional[TagsUpdateDTO] = None


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
    async def create_customer(request: CreateCustomerRequest) -> CreateCustomerResult:
        customer = await customer_store.create_customer(
            name=request.name,
            extra=request.extra if request.extra else {},
        )

        return CreateCustomerResult(
            customer=CustomerDTO(
                id=customer.id,
                creation_utc=customer.creation_utc,
                name=customer.name,
                extra=customer.extra,
                tags=customer.tags,
            )
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
    async def list_customers() -> ListCustomersResult:
        customers = await customer_store.list_customers()

        return ListCustomersResult(
            customers=[
                CustomerDTO(
                    id=customer.id,
                    creation_utc=customer.creation_utc,
                    name=customer.name,
                    extra=customer.extra,
                    tags=customer.tags,
                )
                for customer in customers
            ]
        )

    @router.patch(
        "/{customer_id}",
        operation_id="update_customer",
        status_code=status.HTTP_204_NO_CONTENT,
        **apigen_config(group_name=API_GROUP, method_name="update"),
    )
    async def update_customer(customer_id: CustomerId, request: UpdateCustomerRequest) -> None:
        if request.name:
            params: CustomerUpdateParams = {}
            params["name"] = request.name

            _ = await customer_store.update_customer(
                customer_id=customer_id,
                params=params,
            )

        if request.extra:
            if request.extra.add:
                await customer_store.add_extra(customer_id, request.extra.add)
            if request.extra.remove:
                await customer_store.remove_extra(customer_id, request.extra.remove)

        if request.tags:
            if request.tags.add:
                for tag_id in request.tags.add:
                    await customer_store.add_tag(customer_id, tag_id)
            if request.tags.remove:
                for tag_id in request.tags.remove:
                    await customer_store.remove_tag(customer_id, tag_id)

    return router
