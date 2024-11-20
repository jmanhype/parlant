from datetime import datetime
from fastapi import status
from fastapi.testclient import TestClient
from lagom import Container

from parlant.core.end_users import EndUserStore
from parlant.core.tags import TagStore


def test_that_an_end_user_can_be_created(client: TestClient) -> None:
    name = "John Doe"
    extra = {"email": "john@gmail.com"}

    response = client.post(
        "/end-users",
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

    name = "Menachem Brich"
    extra = {"id": 102938485}

    end_user = await end_user_store.create_end_user(name, extra)

    read_response = client.get(f"/end-users/{end_user.id}")
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

    list_response = client.get("/end-users")
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


async def test_that_an_end_user_can_be_updated_with_a_new_name(
    client: TestClient,
    container: Container,
) -> None:
    end_user_store = container[EndUserStore]

    name = "Original Name"
    extra = {"role": "user"}

    end_user = await end_user_store.create_end_user(name=name, extra=extra)

    new_name = "Updated Name"

    update_response = client.patch(
        f"/end-users/{end_user.id}",
        json={
            "name": new_name,
        },
    )
    assert update_response.status_code == status.HTTP_204_NO_CONTENT

    updated_end_user = await end_user_store.read_end_user(end_user.id)

    assert updated_end_user.name == new_name
    assert updated_end_user.extra == extra


async def test_that_a_tag_can_be_added(
    client: TestClient,
    container: Container,
) -> None:
    end_user_store = container[EndUserStore]
    tag_store = container[TagStore]

    tag = await tag_store.create_tag(name="VIP")

    name = "Tagged User"

    end_user = await end_user_store.create_end_user(name=name)

    update_response = client.patch(
        f"/end-users/{end_user.id}",
        json={
            "tags": {"add": [tag.id]},
        },
    )
    assert update_response.status_code == status.HTTP_204_NO_CONTENT

    updated_end_user = await end_user_store.read_end_user(end_user.id)
    assert tag.id in updated_end_user.tags


async def test_that_a_tag_can_be_removed(
    client: TestClient,
    container: Container,
) -> None:
    end_user_store = container[EndUserStore]
    tag_store = container[TagStore]

    tag = await tag_store.create_tag(name="VIP")

    name = "Tagged User"

    end_user = await end_user_store.create_end_user(name=name)

    await end_user_store.add_tag(end_user_id=end_user.id, tag_id=tag.id)

    update_response = client.patch(
        f"/end-users/{end_user.id}",
        json={
            "tags": {"remove": [tag.id]},
        },
    )
    assert update_response.status_code == status.HTTP_204_NO_CONTENT

    updated_end_user = await end_user_store.read_end_user(end_user.id)
    assert tag.id not in updated_end_user.tags


async def test_that_extra_can_be_added(
    client: TestClient,
    container: Container,
) -> None:
    end_user_store = container[EndUserStore]
    name = "User with Extras"

    end_user = await end_user_store.create_end_user(name=name)

    new_extra = {"department": "sales"}

    update_response = client.patch(
        f"/end-users/{end_user.id}",
        json={
            "extra": {"add": new_extra},
        },
    )
    assert update_response.status_code == status.HTTP_204_NO_CONTENT

    updated_end_user = await end_user_store.read_end_user(end_user.id)
    assert updated_end_user.extra.get("department") == "sales"


async def test_that_extra_can_be_removed(
    client: TestClient,
    container: Container,
) -> None:
    end_user_store = container[EndUserStore]
    name = "User with Extras"

    end_user = await end_user_store.create_end_user(name=name, extra={"department": "sales"})

    update_response = client.patch(
        f"/end-users/{end_user.id}",
        json={
            "extra": {"remove": ["department"]},
        },
    )
    assert update_response.status_code == status.HTTP_204_NO_CONTENT

    updated_end_user = await end_user_store.read_end_user(end_user.id)
    assert "department" not in updated_end_user.extra
