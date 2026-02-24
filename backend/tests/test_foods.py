from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.models.enums import FoodSource, FoodStatus
from app.models.foods import FoodItem

TEST_PASSWORD = "Passw0rd!"


def register_user(
    client: TestClient,
    *,
    email: str,
    username: str,
    password: str = TEST_PASSWORD,
    display_name: str = "User",
) -> dict:
    response = client.post(
        "/auth/register",
        json={
            "email": email,
            "username": username,
            "password": password,
            "display_name": display_name,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def login_and_get_token(client: TestClient, *, identifier: str, password: str = TEST_PASSWORD) -> str:
    response = client.post(
        "/auth/login",
        data={"grant_type": "password", "username": identifier, "password": password},
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def create_food_via_api(client: TestClient, token: str, *, name: str = "Apple") -> dict:
    response = client.post(
        "/foods",
        headers=auth_headers(token),
        json={
            "name": name,
            "brand": "Brand",
            "kcal": "95.00",
            "protein": "0.30",
            "fat": "0.20",
            "carbs": "25.00",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def create_food(
    db_session_factory: sessionmaker[Session],
    *,
    name: str,
    source: FoodSource,
    status: FoodStatus,
    owner_user_id: int | None,
) -> int:
    db_session = db_session_factory()
    try:
        food = FoodItem(
            name=name,
            brand=None,
            kcal=Decimal("100.00"),
            protein=Decimal("10.00"),
            fat=Decimal("5.00"),
            carbs=Decimal("20.00"),
            source=source,
            status=status,
            owner_user_id=owner_user_id,
        )
        db_session.add(food)
        db_session.commit()
        db_session.refresh(food)
        return food.id
    finally:
        db_session.close()


def test_private_food_hidden_from_other_user(client: TestClient, db_session_factory: sessionmaker[Session]) -> None:
    user1 = register_user(client, email="user1@example.com", username="userone")
    register_user(client, email="user2@example.com", username="usertwo")

    private_food_id = create_food(
        db_session_factory,
        name="Private Oatmeal",
        source=FoodSource.private,
        status=FoodStatus.draft,
        owner_user_id=user1["id"],
    )

    token_user2 = login_and_get_token(client, identifier="user2@example.com")
    response = client.get(f"/foods/{private_food_id}", headers=auth_headers(token_user2))

    assert response.status_code == 404, response.text


def test_verified_food_visible_for_both_users(client: TestClient, db_session_factory: sessionmaker[Session]) -> None:
    register_user(client, email="user1@example.com", username="userone")
    register_user(client, email="user2@example.com", username="usertwo")

    verified_food_id = create_food(
        db_session_factory,
        name="Verified Yogurt",
        source=FoodSource.verified,
        status=FoodStatus.pending,
        owner_user_id=None,
    )

    token_user1 = login_and_get_token(client, identifier="user1@example.com")
    token_user2 = login_and_get_token(client, identifier="user2@example.com")

    response_user1 = client.get(f"/foods/{verified_food_id}", headers=auth_headers(token_user1))
    response_user2 = client.get(f"/foods/{verified_food_id}", headers=auth_headers(token_user2))

    assert response_user1.status_code == 200, response_user1.text
    assert response_user2.status_code == 200, response_user2.text
    assert response_user1.json()["id"] == verified_food_id
    assert response_user2.json()["id"] == verified_food_id


def test_search_sorts_my_verified_community_approved(
    client: TestClient,
    db_session_factory: sessionmaker[Session],
) -> None:
    user1 = register_user(client, email="user1@example.com", username="userone")
    user2 = register_user(client, email="user2@example.com", username="usertwo")

    my_food_id = create_food(
        db_session_factory,
        name="zz shared mine",
        source=FoodSource.private,
        status=FoodStatus.draft,
        owner_user_id=user1["id"],
    )
    verified_food_id = create_food(
        db_session_factory,
        name="aa shared verified",
        source=FoodSource.verified,
        status=FoodStatus.approved,
        owner_user_id=None,
    )
    community_approved_food_id = create_food(
        db_session_factory,
        name="bb shared community approved",
        source=FoodSource.community,
        status=FoodStatus.approved,
        owner_user_id=user2["id"],
    )
    create_food(
        db_session_factory,
        name="cc shared community pending",
        source=FoodSource.community,
        status=FoodStatus.pending,
        owner_user_id=user2["id"],
    )

    token_user1 = login_and_get_token(client, identifier="user1@example.com")
    response = client.get(
        "/foods/search",
        headers=auth_headers(token_user1),
        params={"q": "shared"},
    )

    assert response.status_code == 200, response.text
    returned_ids = [item["id"] for item in response.json()]
    assert returned_ids == [my_food_id, verified_food_id, community_approved_food_id]


def test_create_and_publish_food_flow(client: TestClient) -> None:
    user1 = register_user(client, email="user1@example.com", username="userone")
    register_user(client, email="user2@example.com", username="usertwo")

    token_user1 = login_and_get_token(client, identifier="user1@example.com")
    token_user2 = login_and_get_token(client, identifier="user2@example.com")

    create_response = client.post(
        "/foods",
        headers=auth_headers(token_user1),
        json={
            "name": "  Banana  ",
            "brand": "  Local Market  ",
            "kcal": "89.00",
            "protein": "1.10",
            "fat": "0.30",
            "carbs": "22.80",
        },
    )
    assert create_response.status_code == 201, create_response.text
    created_food = create_response.json()
    food_id = created_food["id"]
    assert created_food["name"] == "Banana"
    assert created_food["brand"] == "Local Market"
    assert created_food["owner_user_id"] == user1["id"]
    assert created_food["source"] == "private"
    assert created_food["status"] == "draft"

    response_user2_before_publish = client.get(f"/foods/{food_id}", headers=auth_headers(token_user2))
    assert response_user2_before_publish.status_code == 404, response_user2_before_publish.text

    publish_response = client.post(f"/foods/{food_id}/publish", headers=auth_headers(token_user1))
    assert publish_response.status_code == 200, publish_response.text
    published_food = publish_response.json()
    assert published_food["source"] == "community"
    assert published_food["status"] == "pending"

    response_user2_after_publish = client.get(f"/foods/{food_id}", headers=auth_headers(token_user2))
    assert response_user2_after_publish.status_code == 404, response_user2_after_publish.text

    response_user1_after_publish = client.get(f"/foods/{food_id}", headers=auth_headers(token_user1))
    assert response_user1_after_publish.status_code == 200, response_user1_after_publish.text
    assert response_user1_after_publish.json()["id"] == food_id


def test_patch_and_delete_food_happy_path(client: TestClient) -> None:
    register_user(client, email="user1@example.com", username="userone")
    token_user1 = login_and_get_token(client, identifier="user1@example.com")

    created_food = create_food_via_api(client, token_user1, name="  Initial name  ")
    food_id = created_food["id"]

    patch_response = client.patch(
        f"/foods/{food_id}",
        headers=auth_headers(token_user1),
        json={
            "name": "  Updated name  ",
            "brand": "   ",
            "kcal": "120.00",
            "protein": "2.20",
            "fat": "0.90",
            "carbs": "27.30",
        },
    )
    assert patch_response.status_code == 200, patch_response.text
    patched_food = patch_response.json()
    assert patched_food["name"] == "Updated name"
    assert patched_food["brand"] is None
    assert Decimal(str(patched_food["kcal"])) == Decimal("120.00")
    assert Decimal(str(patched_food["protein"])) == Decimal("2.20")
    assert Decimal(str(patched_food["fat"])) == Decimal("0.90")
    assert Decimal(str(patched_food["carbs"])) == Decimal("27.30")

    delete_response = client.delete(f"/foods/{food_id}", headers=auth_headers(token_user1))
    assert delete_response.status_code == 204, delete_response.text

    get_after_delete = client.get(f"/foods/{food_id}", headers=auth_headers(token_user1))
    assert get_after_delete.status_code == 404, get_after_delete.text


def test_foreign_user_cannot_patch_or_delete_food(client: TestClient) -> None:
    register_user(client, email="user1@example.com", username="userone")
    register_user(client, email="user2@example.com", username="usertwo")

    token_user1 = login_and_get_token(client, identifier="user1@example.com")
    token_user2 = login_and_get_token(client, identifier="user2@example.com")

    created_food = create_food_via_api(client, token_user1, name="Owned food")
    food_id = created_food["id"]

    patch_response = client.patch(
        f"/foods/{food_id}",
        headers=auth_headers(token_user2),
        json={"name": "Hacked"},
    )
    assert patch_response.status_code == 404, patch_response.text

    delete_response = client.delete(f"/foods/{food_id}", headers=auth_headers(token_user2))
    assert delete_response.status_code == 404, delete_response.text


def test_patch_food_name_blank_returns_422(client: TestClient) -> None:
    register_user(client, email="user1@example.com", username="userone")
    token_user1 = login_and_get_token(client, identifier="user1@example.com")
    created_food = create_food_via_api(client, token_user1)
    food_id = created_food["id"]

    response = client.patch(
        f"/foods/{food_id}",
        headers=auth_headers(token_user1),
        json={"name": "   "},
    )
    assert response.status_code == 422, response.text


def test_patch_food_negative_kcal_returns_422(client: TestClient) -> None:
    register_user(client, email="user1@example.com", username="userone")
    token_user1 = login_and_get_token(client, identifier="user1@example.com")
    created_food = create_food_via_api(client, token_user1)
    food_id = created_food["id"]

    response = client.patch(
        f"/foods/{food_id}",
        headers=auth_headers(token_user1),
        json={"kcal": "-1"},
    )
    assert response.status_code == 422, response.text


def test_patch_and_delete_after_publish_return_409(client: TestClient) -> None:
    register_user(client, email="user1@example.com", username="userone")
    token_user1 = login_and_get_token(client, identifier="user1@example.com")
    created_food = create_food_via_api(client, token_user1)
    food_id = created_food["id"]

    publish_response = client.post(f"/foods/{food_id}/publish", headers=auth_headers(token_user1))
    assert publish_response.status_code == 200, publish_response.text

    patch_response = client.patch(
        f"/foods/{food_id}",
        headers=auth_headers(token_user1),
        json={"name": "Try update"},
    )
    assert patch_response.status_code == 409, patch_response.text

    delete_response = client.delete(f"/foods/{food_id}", headers=auth_headers(token_user1))
    assert delete_response.status_code == 409, delete_response.text
