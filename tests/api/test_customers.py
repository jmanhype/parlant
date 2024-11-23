from datetime import datetime
from fastapi import status
from fastapi.testclient import TestClient
from lagom import Container
from pytest import raises

from parlant.core.common import ItemNotFoundError
from parlant.core.customers import CustomerStore
from parlant.core.tags import TagStore


def test_that_a_customer_can_be_created(client: TestClient) -> None:
    name = "John Doe"
    extra = {"email": "john@gmail.com"}

    response = client.post(
        "/customers",
        json={
            "name": name,
            "extra": extra,
        },
    )

    assert response.status_code == status.HTTP_201_CREATED

    customer = response.json()
    assert customer["name"] == name
    assert customer["extra"] == extra
    assert "id" in customer
    assert "creation_utc" in customer


async def test_that_a_customer_can_be_read(
    client: TestClient,
    container: Container,
) -> None:
    customer_store = container[CustomerStore]

    name = "Menachem Brich"
    extra = {"id": str(102938485)}

    customer = await customer_store.create_customer(name, extra)

    read_response = client.get(f"/customers/{customer.id}")
    assert read_response.status_code == status.HTTP_200_OK

    data = read_response.json()
    assert data["id"] == customer.id
    assert data["name"] == name
    assert data["extra"] == extra
    assert datetime.fromisoformat(data["creation_utc"]) == customer.creation_utc


async def test_that_customers_can_be_listed(
    client: TestClient,
    container: Container,
) -> None:
    customer_store = container[CustomerStore]

    first_name = "YamChuk"
    first_extra = {"address": "Hawaii"}

    second_name = "DorZo"
    second_extra = {"address": "Alaska"}

    await customer_store.create_customer(
        name=first_name,
        extra=first_extra,
    )

    await customer_store.create_customer(
        name=second_name,
        extra=second_extra,
    )

    customers = client.get("/customers").raise_for_status().json()

    assert len(customers) == 2
    assert any(
        first_name == customer["name"] and first_extra == customer["extra"]
        for customer in customers
    )
    assert any(
        second_name == customer["name"] and second_extra == customer["extra"]
        for customer in customers
    )


async def test_that_a_customer_can_be_updated_with_a_new_name(
    client: TestClient,
    container: Container,
) -> None:
    customer_store = container[CustomerStore]

    name = "Original Name"
    extra = {"role": "customer"}

    customer = await customer_store.create_customer(name=name, extra=extra)

    new_name = "Updated Name"

    update_response = client.patch(
        f"/customers/{customer.id}",
        json={
            "name": new_name,
        },
    )
    assert update_response.status_code == status.HTTP_204_NO_CONTENT

    updated_customer = await customer_store.read_customer(customer.id)

    assert updated_customer.name == new_name
    assert updated_customer.extra == extra


async def test_that_a_customer_can_be_deleted(
    client: TestClient,
    container: Container,
) -> None:
    customer_store = container[CustomerStore]

    name = "Original Name"

    customer = await customer_store.create_customer(name=name)

    delete_response = client.delete(f"/customers/{customer.id}")
    assert delete_response.status_code == status.HTTP_204_NO_CONTENT

    with raises(ItemNotFoundError):
        await customer_store.read_customer(customer.id)


async def test_that_a_tag_can_be_added(
    client: TestClient,
    container: Container,
) -> None:
    customer_store = container[CustomerStore]
    tag_store = container[TagStore]

    tag = await tag_store.create_tag(name="VIP")

    name = "Tagged Customer"

    customer = await customer_store.create_customer(name=name)

    update_response = client.patch(
        f"/customers/{customer.id}",
        json={
            "tags": {"add": [tag.id]},
        },
    )
    assert update_response.status_code == status.HTTP_204_NO_CONTENT

    updated_customer = await customer_store.read_customer(customer.id)
    assert tag.id in updated_customer.tags


async def test_that_a_tag_can_be_removed(
    client: TestClient,
    container: Container,
) -> None:
    customer_store = container[CustomerStore]
    tag_store = container[TagStore]

    tag = await tag_store.create_tag(name="VIP")

    name = "Tagged Customer"

    customer = await customer_store.create_customer(name=name)

    await customer_store.add_tag(customer_id=customer.id, tag_id=tag.id)

    update_response = client.patch(
        f"/customers/{customer.id}",
        json={
            "tags": {"remove": [tag.id]},
        },
    )
    assert update_response.status_code == status.HTTP_204_NO_CONTENT

    updated_customer = await customer_store.read_customer(customer.id)
    assert tag.id not in updated_customer.tags


async def test_that_extra_can_be_added(
    client: TestClient,
    container: Container,
) -> None:
    customer_store = container[CustomerStore]
    name = "Customer with Extras"

    customer = await customer_store.create_customer(name=name)

    new_extra = {"department": "sales"}

    update_response = client.patch(
        f"/customers/{customer.id}",
        json={
            "extra": {"add": new_extra},
        },
    )
    assert update_response.status_code == status.HTTP_204_NO_CONTENT

    updated_customer = await customer_store.read_customer(customer.id)
    assert updated_customer.extra.get("department") == "sales"


async def test_that_extra_can_be_removed(
    client: TestClient,
    container: Container,
) -> None:
    customer_store = container[CustomerStore]
    name = "Customer with Extras"

    customer = await customer_store.create_customer(name=name, extra={"department": "sales"})

    update_response = client.patch(
        f"/customers/{customer.id}",
        json={
            "extra": {"remove": ["department"]},
        },
    )
    assert update_response.status_code == status.HTTP_204_NO_CONTENT

    updated_customer = await customer_store.read_customer(customer.id)
    assert "department" not in updated_customer.extra
