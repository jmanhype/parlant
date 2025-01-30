import dateutil.parser
from fastapi import status
import httpx
from lagom import Container
from pytest import raises

from parlant.core.common import ItemNotFoundError
from parlant.core.fragments import FragmentStore, Slot
from parlant.core.tags import TagStore


async def test_that_a_fragment_can_be_created(
    async_client: httpx.AsyncClient,
) -> None:
    payload = {
        "value": "Your account balance is {balance}",
        "slots": [
            {
                "name": "balance",
                "description": "Account's balance",
                "examples": ["9000"],
            }
        ],
    }

    response = await async_client.post("/fragments", json=payload)
    assert response.status_code == status.HTTP_201_CREATED

    fragment = response.json()

    assert fragment["value"] == payload["value"]
    assert fragment["slots"] == payload["slots"]

    assert "id" in fragment
    assert "creation_utc" in fragment


async def test_that_a_fragment_can_be_read(
    async_client: httpx.AsyncClient,
    container: Container,
) -> None:
    fragment_store = container[FragmentStore]

    value = "Your account balance is {balance}"
    slots = [Slot(name="balance", description="Account's balance", examples=["9000"])]

    fragment = await fragment_store.create_fragment(value=value, slots=slots)

    response = await async_client.get(f"/fragments/{fragment.id}")
    assert response.status_code == status.HTTP_200_OK

    data = response.json()
    assert data["id"] == fragment.id
    assert data["value"] == value

    assert len(data["slots"]) == 1
    slot = data["slots"][0]
    assert slot["name"] == slots[0].name
    assert slot["description"] == slots[0].description
    assert slot["examples"] == slots[0].examples

    assert dateutil.parser.parse(data["creation_utc"]) == fragment.creation_utc


async def test_that_all_fragments_can_be_listed(
    async_client: httpx.AsyncClient,
    container: Container,
) -> None:
    fragment_store = container[FragmentStore]

    first_value = "Your account balance is {balance}"
    first_slots = [Slot(name="balance", description="Account's balance", examples=["9000"])]

    second_value = "It will take {days_number} days to deliver to {address}"
    second_slots = [
        Slot(name="days_number", description="Time required for delivery in days", examples=["8"]),
        Slot(name="address", description="Customer's address", examples=["Some Address"]),
    ]

    await fragment_store.create_fragment(value=first_value, slots=first_slots)
    await fragment_store.create_fragment(value=second_value, slots=second_slots)

    response = await async_client.get("/fragments")
    assert response.status_code == status.HTTP_200_OK
    fragments = response.json()

    assert len(fragments) >= 2
    assert any(f["value"] == first_value for f in fragments)
    assert any(f["value"] == second_value for f in fragments)


async def test_that_a_fragment_can_be_updated(
    async_client: httpx.AsyncClient,
    container: Container,
) -> None:
    fragment_store = container[FragmentStore]

    value = "Your account balance is {balance}"
    slots = [Slot(name="balance", description="Account's balance", examples=["9000"])]

    fragment = await fragment_store.create_fragment(value=value, slots=slots)

    update_payload = {
        "value": "Updated balance: {balance}",
        "slots": [
            {
                "name": "balance",
                "description": "Updated account balance",
                "examples": ["10000"],
            }
        ],
    }

    response = await async_client.patch(f"/fragments/{fragment.id}", json=update_payload)
    assert response.status_code == status.HTTP_200_OK

    updated_fragment = response.json()
    assert updated_fragment["value"] == update_payload["value"]
    assert updated_fragment["slots"] == update_payload["slots"]


async def test_that_a_fragment_can_be_deleted(
    async_client: httpx.AsyncClient,
    container: Container,
) -> None:
    fragment_store = container[FragmentStore]

    value = "Your account balance is {balance}"
    slots = [Slot(name="balance", description="Account's balance", examples=["9000"])]

    fragment = await fragment_store.create_fragment(value=value, slots=slots)

    delete_response = await async_client.delete(f"/fragments/{fragment.id}")
    assert delete_response.status_code == status.HTTP_204_NO_CONTENT

    with raises(ItemNotFoundError):
        await fragment_store.read_fragment(fragment.id)


async def test_that_a_tag_can_be_added_to_a_fragment(
    async_client: httpx.AsyncClient,
    container: Container,
) -> None:
    fragment_store = container[FragmentStore]
    tag_store = container[TagStore]

    tag = await tag_store.create_tag(name="VIP")

    value = "Your account balance is {balance}"
    slots = [Slot(name="balance", description="Account's balance", examples=["9000"])]

    fragment = await fragment_store.create_fragment(value=value, slots=slots)

    response = await async_client.patch(
        f"/fragments/{fragment.id}", json={"tags": {"add": [tag.id]}}
    )
    assert response.status_code == status.HTTP_200_OK

    updated_fragment = await fragment_store.read_fragment(fragment.id)
    assert tag.id in updated_fragment.tags


async def test_that_a_tag_can_be_removed_from_a_fragment(
    async_client: httpx.AsyncClient,
    container: Container,
) -> None:
    fragment_store = container[FragmentStore]
    tag_store = container[TagStore]

    tag = await tag_store.create_tag(name="VIP")

    value = "Your account balance is {balance}"
    slots = [Slot(name="balance", description="Account's balance", examples=["9000"])]

    fragment = await fragment_store.create_fragment(value=value, slots=slots)

    await fragment_store.add_tag(fragment_id=fragment.id, tag_id=tag.id)
    response = await async_client.patch(
        f"/fragments/{fragment.id}", json={"tags": {"remove": [tag.id]}}
    )
    assert response.status_code == status.HTTP_200_OK

    updated_fragment = await fragment_store.read_fragment(fragment.id)
    assert tag.id not in updated_fragment.tags
