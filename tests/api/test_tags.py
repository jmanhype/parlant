from datetime import datetime
from fastapi import status
from fastapi.testclient import TestClient
from lagom import Container
from pytest import raises

from parlant.core.common import ItemNotFoundError
from parlant.core.tags import TagStore


def test_that_a_tag_can_be_created(client: TestClient) -> None:
    label = "VIP"

    response = client.post(
        "/tags",
        json={
            "label": label,
        },
    )

    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()

    assert "tag" in data
    tag = data["tag"]
    assert tag["label"] == label
    assert "id" in tag
    assert "creation_utc" in tag


async def test_that_a_tag_can_be_read(
    client: TestClient,
    container: Container,
) -> None:
    tag_store = container[TagStore]

    label = "VIP"

    tag = await tag_store.create_tag(label)

    read_response = client.get(f"/tags/{tag.id}")
    assert read_response.status_code == status.HTTP_200_OK

    data = read_response.json()
    assert data["id"] == tag.id
    assert data["label"] == label
    assert datetime.fromisoformat(data["creation_utc"]) == tag.creation_utc


async def test_that_tags_can_be_listed(
    client: TestClient,
    container: Container,
) -> None:
    tag_store = container[TagStore]

    first_label = "VIP"
    second_label = "Female"

    _ = await tag_store.create_tag(first_label)
    _ = await tag_store.create_tag(second_label)

    list_response = client.get("/tags")
    assert list_response.status_code == status.HTTP_200_OK

    data = list_response.json()
    assert "tags" in data
    tag_list = data["tags"]

    assert len(tag_list) == 2
    assert any(first_label == tag["label"] for tag in tag_list)
    assert any(second_label == tag["label"] for tag in tag_list)


async def test_that_a_tag_can_be_updated(
    client: TestClient,
    container: Container,
) -> None:
    tag_store = container[TagStore]

    old_label = "VIP"

    tag = await tag_store.create_tag(old_label)

    new_label = "Alpha"
    update_response = client.patch(
        f"/tags/{tag.id}",
        json={
            "label": new_label,
        },
    )
    assert update_response.status_code == status.HTTP_204_NO_CONTENT

    updated_tag = await tag_store.read_tag(tag.id)
    assert updated_tag.label == new_label


async def test_that_a_tag_can_be_deleted(
    client: TestClient,
    container: Container,
) -> None:
    tag_store = container[TagStore]

    label = "VIP"

    tag = await tag_store.create_tag(label)

    delete_response = client.delete(f"/tags/{tag.id}")
    assert delete_response.status_code == status.HTTP_200_OK

    data = delete_response.json()
    assert data["tag_id"] == tag.id

    with raises(ItemNotFoundError):
        _ = await tag_store.read_tag(tag.id)
