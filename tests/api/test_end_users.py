from datetime import datetime
from fastapi import status
from fastapi.testclient import TestClient
from lagom import Container

from parlant.core.end_users import EndUserStore


def test_that_an_end_user_can_be_created(client: TestClient) -> None:
    name = "John Doe"
    extra = {"email": "john@gmail.com"}

    response = client.post(
        "/end_users",
        json={
            "name": name,
            "extra": extra,
        },
    )

    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()

    assert "end_user" in data
    end_user = data["end_user"]
    assert end_user["name"] == name
    assert end_user["extra"] == extra
    assert "id" in end_user
    assert "creation_utc" in end_user


async def test_that_an_end_user_can_be_read(
    client: TestClient,
    container: Container,
) -> None:
    end_user_store = container[EndUserStore]
    name = "Alice Johnson"
    extra = {"id": 102938485}

    end_user = await end_user_store.create_end_user(name, extra)

    read_response = client.get(f"/end_users/{end_user.id}")
    assert read_response.status_code == status.HTTP_200_OK

    data = read_response.json()
    assert data["id"] == end_user.id
    assert data["name"] == name
    assert data["extra"] == extra
    assert datetime.fromisoformat(data["creation_utc"]) == end_user.creation_utc


async def test_that_end_users_can_be_listed(
    client: TestClient,
    container: Container,
) -> None:
    end_user_store = container[EndUserStore]

    first_name = "YamChuk"
    first_extra = {"address": "Hertzeliya"}

    second_name = "DorZo"
    second_extra = {"address": "Givatayim"}

    await end_user_store.create_end_user(
        name=first_name,
        extra=first_extra,
    )

    await end_user_store.create_end_user(
        name=second_name,
        extra=second_extra,
    )

    list_response = client.get("/end_users")
    assert list_response.status_code == status.HTTP_200_OK
    data = list_response.json()
    assert "end_users" in data
    end_users_list = data["end_users"]
    assert len(end_users_list) == 2

    assert any(
        first_name == end_user["name"] and first_extra == end_user["extra"]
        for end_user in end_users_list
    )
    assert any(
        second_name == end_user["name"] and second_extra == end_user["extra"]
        for end_user in end_users_list
    )


async def test_that_an_end_user_can_be_updated(
    client: TestClient,
    container: Container,
) -> None:
    end_user_store = container[EndUserStore]

    name = "Old Name"
    extra = {"age": 40}

    end_user = await end_user_store.create_end_user(name=name, extra=extra)

    new_name = "New Name"
    new_extra = {"age": 45}

    patch_response = client.patch(
        f"/end_users/{end_user.id}",
        json={
            "name": new_name,
            "extra": new_extra,
        },
    )
    assert patch_response.status_code == status.HTTP_200_OK
    updated_end_user = patch_response.json()
    assert updated_end_user["name"] == new_name
    assert updated_end_user["extra"] == new_extra


async def test_that_a_tag_can_be_created(
    client: TestClient,
    container: Container,
) -> None:
    end_user_store = container[EndUserStore]

    name = "Tagged User"
    end_user = await end_user_store.create_end_user(name)

    label = "VIP"

    tag_response = client.post(
        f"/end_users/{end_user.id}/tags",
        json={
            "label": label,
        },
    )
    assert tag_response.status_code == status.HTTP_201_CREATED

    tag = tag_response.json()
    assert tag["label"] == label
    assert "id" in tag
    assert "creation_utc" in tag


async def test_that_tags_can_be_listed_by_end_user(
    client: TestClient,
    container: Container,
) -> None:
    end_user_store = container[EndUserStore]

    name = "User with Tags"
    end_user = await end_user_store.create_end_user(name)

    first_tag = await end_user_store.set_tag(end_user.id, label="VIP")
    second_tag = await end_user_store.set_tag(end_user.id, label="Beta Tester")

    list_response = client.get(f"/end_users/{end_user.id}/tags")
    assert list_response.status_code == status.HTTP_200_OK

    data = list_response.json()

    assert "tags" in data
    tags = data["tags"]
    assert len(tags) == 2

    assert any(first_tag.label == t["label"] for t in tags)
    assert any(second_tag.label == t["label"] for t in tags)


async def test_that_a_tag_associated_to_an_end_user_can_be_deleted(
    client: TestClient,
    container: Container,
) -> None:
    end_user_store = container[EndUserStore]

    name = "Moses"
    end_user = await end_user_store.create_end_user(name)

    label = "Temporary Tag"
    tag = await end_user_store.set_tag(end_user_id=end_user.id, label=label)

    delete_response = client.delete(f"/end_users/{end_user.id}/tags/{tag.id}")
    assert delete_response.status_code == status.HTTP_200_OK
    data = delete_response.json()
    assert data["tag_id"] == tag.id

    tags = await end_user_store.get_tags(end_user.id)
    assert len(tags) == 0
