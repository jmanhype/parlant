from datetime import datetime
from fastapi import status
from fastapi.testclient import TestClient
from lagom import Container
from pytest import raises

from parlant.core.common import ItemNotFoundError
from parlant.core.tags import TagStore


def test_that_a_tag_can_be_created(client: TestClient) -> None:
    name = "VIP"

    response = client.post(
        "/tags",
        json={
            "name": name,
        },
    )

    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()

    assert "tag" in data
    tag = data["tag"]
    assert tag["name"] == name
    assert "id" in tag
    assert "creation_utc" in tag


async def test_that_a_tag_can_be_read(
    client: TestClient,
    container: Container,
) -> None:
    tag_store = container[TagStore]

    name = "VIP"

    tag = await tag_store.create_tag(name)

    read_response = client.get(f"/tags/{tag.id}")
    assert read_response.status_code == status.HTTP_200_OK

    data = read_response.json()
    assert data["id"] == tag.id
    assert data["name"] == name
    assert datetime.fromisoformat(data["creation_utc"]) == tag.creation_utc


async def test_that_tags_can_be_listed(
    client: TestClient,
    container: Container,
) -> None:
    tag_store = container[TagStore]

    first_name = "VIP"
    second_name = "Female"

    _ = await tag_store.create_tag(first_name)
    _ = await tag_store.create_tag(second_name)

    list_response = client.get("/tags")
    assert list_response.status_code == status.HTTP_200_OK

    data = list_response.json()
    assert "tags" in data
    tag_list = data["tags"]

    assert len(tag_list) == 2
    assert any(first_name == tag["name"] for tag in tag_list)
    assert any(second_name == tag["name"] for tag in tag_list)


async def test_that_a_tag_can_be_updated(
    client: TestClient,
    container: Container,
) -> None:
    tag_store = container[TagStore]

    old_name = "VIP"

    tag = await tag_store.create_tag(old_name)

    new_name = "Alpha"
    update_response = client.patch(
        f"/tags/{tag.id}",
        json={
            "name": new_name,
        },
    )
    assert update_response.status_code == status.HTTP_204_NO_CONTENT

    updated_tag = await tag_store.read_tag(tag.id)
    assert updated_tag.name == new_name


async def test_that_a_tag_can_be_deleted(
    client: TestClient,
    container: Container,
) -> None:
    tag_store = container[TagStore]

    name = "VIP"

    tag = await tag_store.create_tag(name)

    client.delete(f"/tags/{tag.id}")

    with raises(ItemNotFoundError):
        _ = await tag_store.read_tag(tag.id)
