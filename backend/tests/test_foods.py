from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.models.enums import FoodSource, FoodStatus, UserRole
from app.models.foods import FoodItem
from app.services.security import hash_password
from app.services.foods import seed_verified_foods
from app.services.users import create_user

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


def create_food_with_payload(client: TestClient, token: str, payload: dict) -> dict:
    response = client.post(
        "/foods",
        headers=auth_headers(token),
        json=payload,
    )
    assert response.status_code == 201, response.text
    return response.json()


def create_serving_via_api(client: TestClient, token: str, food_id: int, *, name: str = "1 cup", grams: str = "250") -> dict:
    response = client.post(
        f"/foods/{food_id}/servings",
        headers=auth_headers(token),
        json={
            "name": name,
            "grams": grams,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def create_admin_user(db_session_factory: sessionmaker[Session], *, email: str = "admin@example.com") -> None:
    db_session = db_session_factory()
    try:
        create_user(
            db=db_session,
            email=email,
            username="admin",
            display_name="Admin",
            hashed_password=hash_password(TEST_PASSWORD),
            role=UserRole.admin,
        )
    finally:
        db_session.close()


def create_food(
    db_session_factory: sessionmaker[Session],
    *,
    name: str,
    brand: str | None = None,
    source: FoodSource,
    status: FoodStatus,
    owner_user_id: int | None,
    is_listed: bool = True,
) -> int:
    db_session = db_session_factory()
    try:
        food = FoodItem(
            name=name,
            brand=brand,
            kcal=Decimal("100.00"),
            protein=Decimal("10.00"),
            fat=Decimal("5.00"),
            carbs=Decimal("20.00"),
            source=source,
            status=status,
            owner_user_id=owner_user_id,
            is_listed=is_listed,
        )
        db_session.add(food)
        db_session.commit()
        db_session.refresh(food)
        return food.id
    finally:
        db_session.close()


def test_create_food_default_category_is_other(client: TestClient) -> None:
    register_user(client, email="food_category_default@example.com", username="food_category_default")
    token = login_and_get_token(client, identifier="food_category_default@example.com")

    created = create_food_with_payload(
        client,
        token,
        {
            "name": "Category Default Food",
            "kcal": "100.00",
            "protein": "10.00",
            "fat": "5.00",
            "carbs": "20.00",
        },
    )

    assert created["category"] == "other"
    assert Decimal(str(created["fiber"])) == Decimal("0")


def test_create_food_with_fiber_and_patch_fiber(client: TestClient) -> None:
    register_user(client, email="food_fiber_create@example.com", username="food_fiber_create")
    token = login_and_get_token(client, identifier="food_fiber_create@example.com")

    created = create_food_with_payload(
        client,
        token,
        {
            "name": "Продукт с клетчаткой",
            "kcal": "100.00",
            "protein": "10.00",
            "fat": "5.00",
            "carbs": "20.00",
            "fiber": "7.50",
        },
    )
    assert Decimal(str(created["fiber"])) == Decimal("7.50")

    patched = client.patch(
        f"/foods/{created['id']}",
        headers=auth_headers(token),
        json={"fiber": "3.25"},
    )
    assert patched.status_code == 200, patched.text
    assert Decimal(str(patched.json()["fiber"])) == Decimal("3.25")

    detail = client.get(f"/foods/{created['id']}", headers=auth_headers(token))
    assert detail.status_code == 200, detail.text
    assert Decimal(str(detail.json()["fiber"])) == Decimal("3.25")

    search = client.get("/foods/search", headers=auth_headers(token), params={"q": "клетчаткой"})
    assert search.status_code == 200, search.text
    found = next(item for item in search.json() if item["id"] == created["id"])
    assert Decimal(str(found["fiber"])) == Decimal("3.25")


def test_food_fiber_validation_for_create_and_patch(client: TestClient) -> None:
    register_user(client, email="food_fiber_invalid@example.com", username="food_fiber_invalid")
    token = login_and_get_token(client, identifier="food_fiber_invalid@example.com")

    create_negative = client.post(
        "/foods",
        headers=auth_headers(token),
        json={
            "name": "Negative fiber",
            "kcal": "100.00",
            "protein": "10.00",
            "fat": "5.00",
            "carbs": "20.00",
            "fiber": "-1.00",
        },
    )
    assert create_negative.status_code == 422, create_negative.text

    create_too_high = client.post(
        "/foods",
        headers=auth_headers(token),
        json={
            "name": "Too high fiber",
            "kcal": "100.00",
            "protein": "10.00",
            "fat": "5.00",
            "carbs": "20.00",
            "fiber": "101.00",
        },
    )
    assert create_too_high.status_code == 422, create_too_high.text

    created = create_food_with_payload(
        client,
        token,
        {
            "name": "Fiber patch source",
            "kcal": "100.00",
            "protein": "10.00",
            "fat": "5.00",
            "carbs": "20.00",
        },
    )
    patch_invalid = client.patch(
        f"/foods/{created['id']}",
        headers=auth_headers(token),
        json={"fiber": "150.00"},
    )
    assert patch_invalid.status_code == 422, patch_invalid.text


def test_create_food_with_category_and_patch_category(client: TestClient) -> None:
    register_user(client, email="food_category_patch@example.com", username="food_category_patch")
    token = login_and_get_token(client, identifier="food_category_patch@example.com")

    created = create_food_with_payload(
        client,
        token,
        {
            "name": "Category Patch Food",
            "kcal": "100.00",
            "protein": "10.00",
            "fat": "5.00",
            "carbs": "20.00",
            "category": "fruits",
        },
    )
    assert created["category"] == "fruits"

    patched = client.patch(
        f"/foods/{created['id']}",
        headers=auth_headers(token),
        json={"category": "vegetables"},
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["category"] == "vegetables"

    detail = client.get(f"/foods/{created['id']}", headers=auth_headers(token))
    assert detail.status_code == 200, detail.text
    assert detail.json()["category"] == "vegetables"

    search = client.get("/foods/search", headers=auth_headers(token), params={"q": "Category Patch"})
    assert search.status_code == 200, search.text
    assert any(item["id"] == created["id"] and item["category"] == "vegetables" for item in search.json())


def test_food_category_validation_for_create_and_patch(client: TestClient) -> None:
    register_user(client, email="food_category_invalid@example.com", username="food_category_invalid")
    token = login_and_get_token(client, identifier="food_category_invalid@example.com")

    create_invalid = client.post(
        "/foods",
        headers=auth_headers(token),
        json={
            "name": "Category Invalid Food",
            "kcal": "100.00",
            "protein": "10.00",
            "fat": "5.00",
            "carbs": "20.00",
            "category": "invalid_category",
        },
    )
    assert create_invalid.status_code == 422, create_invalid.text

    created = create_food_with_payload(
        client,
        token,
        {
            "name": "Category Patch Invalid Food",
            "kcal": "100.00",
            "protein": "10.00",
            "fat": "5.00",
            "carbs": "20.00",
        },
    )
    patch_invalid = client.patch(
        f"/foods/{created['id']}",
        headers=auth_headers(token),
        json={"category": "invalid_category"},
    )
    assert patch_invalid.status_code == 422, patch_invalid.text


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


def test_seed_verified_foods_idempotent(db_session_factory: sessionmaker[Session]) -> None:
    db_session = db_session_factory()
    try:
        created_first = seed_verified_foods(db_session)
        count_after_first = db_session.execute(
            select(func.count(FoodItem.id)).where(FoodItem.source == FoodSource.verified)
        ).scalar_one()

        created_second = seed_verified_foods(db_session)
        count_after_second = db_session.execute(
            select(func.count(FoodItem.id)).where(FoodItem.source == FoodSource.verified)
        ).scalar_one()
        egg_category = db_session.execute(
            select(FoodItem).where(
                FoodItem.source == FoodSource.verified,
                FoodItem.name == "Яйцо куриное",
            )
        ).scalar_one().category
        foods_with_fiber = db_session.execute(
            select(func.count(FoodItem.id)).where(
                FoodItem.source == FoodSource.verified,
                FoodItem.fiber > 0,
            )
        ).scalar_one()
        animal_fiber = db_session.execute(
            select(FoodItem.fiber).where(
                FoodItem.source == FoodSource.verified,
                FoodItem.name == "Яйцо куриное",
            )
        ).scalar_one()
    finally:
        db_session.close()

    assert created_first >= 20
    assert created_second == 0
    assert count_after_second == count_after_first
    assert egg_category == "eggs"
    assert int(foods_with_fiber or 0) > 0
    assert Decimal(str(animal_fiber)) == Decimal("0")


def test_seed_verified_foods_have_plausible_fiber_for_cooked_grains_and_legumes(
    db_session_factory: sessionmaker[Session],
) -> None:
    db_session = db_session_factory()
    try:
        seed_verified_foods(db_session, replace_existing_values=True)
        foods = db_session.execute(
            select(FoodItem).where(FoodItem.source == FoodSource.verified)
        ).scalars().all()
        by_name = {food.name: food for food in foods}
    finally:
        db_session.close()

    cooked_grain_ranges = {
        "Рис отварной": (Decimal("0.30"), Decimal("1.50")),
        "Гречка отварная": (Decimal("2.50"), Decimal("4.00")),
        "Булгур отварной": (Decimal("1.50"), Decimal("4.00")),
        "Кускус отварной": (Decimal("1.00"), Decimal("2.00")),
        "Киноа отварная": (Decimal("2.00"), Decimal("3.50")),
    }
    cooked_legume_ranges = {
        "Нут вареный": (Decimal("5.00"), Decimal("8.00")),
        "Фасоль красная вареная": (Decimal("5.00"), Decimal("8.00")),
        "Чечевица вареная": (Decimal("5.00"), Decimal("8.00")),
    }
    zero_fiber_products = ["Куриная грудка", "Лосось", "Яйцо куриное", "Творог 5%", "Оливковое масло"]

    for name, (lower, upper) in {**cooked_grain_ranges, **cooked_legume_ranges}.items():
        assert name in by_name
        value = Decimal(str(by_name[name].fiber))
        assert lower <= value <= upper

    for name in zero_fiber_products:
        assert name in by_name
        assert Decimal(str(by_name[name].fiber)) == Decimal("0")


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


def test_search_starts_with_ranked_above_contains(client: TestClient, db_session_factory: sessionmaker[Session]) -> None:
    register_user(client, email="user1@example.com", username="userone")
    token_user1 = login_and_get_token(client, identifier="user1@example.com")

    apple_id = create_food(
        db_session_factory,
        name="Apple",
        source=FoodSource.verified,
        status=FoodStatus.approved,
        owner_user_id=None,
    )
    applesauce_id = create_food(
        db_session_factory,
        name="Applesauce",
        source=FoodSource.verified,
        status=FoodStatus.approved,
        owner_user_id=None,
    )
    pineapple_id = create_food(
        db_session_factory,
        name="Pineapple",
        source=FoodSource.verified,
        status=FoodStatus.approved,
        owner_user_id=None,
    )

    response = client.get("/foods/search", headers=auth_headers(token_user1), params={"q": "app"})
    assert response.status_code == 200, response.text
    result_ids = [item["id"] for item in response.json()]
    assert result_ids.index(apple_id) < result_ids.index(pineapple_id)
    assert result_ids.index(applesauce_id) < result_ids.index(pineapple_id)

    milk_id = create_food(
        db_session_factory,
        name="Milk",
        brand="Alpro",
        source=FoodSource.verified,
        status=FoodStatus.approved,
        owner_user_id=None,
    )
    yogurt_id = create_food(
        db_session_factory,
        name="Yogurt",
        brand="Calpro",
        source=FoodSource.verified,
        status=FoodStatus.approved,
        owner_user_id=None,
    )

    brand_response = client.get("/foods/search", headers=auth_headers(token_user1), params={"q": "alp"})
    assert brand_response.status_code == 200, brand_response.text
    brand_result_ids = [item["id"] for item in brand_response.json()]
    assert brand_result_ids.index(milk_id) < brand_result_ids.index(yogurt_id)


def test_search_keeps_source_priority_owned_before_verified(client: TestClient, db_session_factory: sessionmaker[Session]) -> None:
    register_user(client, email="user1@example.com", username="userone")
    token_user1 = login_and_get_token(client, identifier="user1@example.com")

    owned_food = create_food_via_api(client, token_user1, name="Apple Pie")
    owned_food_id = owned_food["id"]
    verified_food_id = create_food(
        db_session_factory,
        name="Apple Juice",
        source=FoodSource.verified,
        status=FoodStatus.approved,
        owner_user_id=None,
    )

    response = client.get("/foods/search", headers=auth_headers(token_user1), params={"q": "app"})
    assert response.status_code == 200, response.text
    result_ids = [item["id"] for item in response.json()]
    assert result_ids.index(owned_food_id) < result_ids.index(verified_food_id)


def test_publish_food_sets_approved(client: TestClient) -> None:
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
    assert published_food["status"] == "approved"
    assert published_food["is_listed"] is True

    response_user2_after_publish = client.get(f"/foods/{food_id}", headers=auth_headers(token_user2))
    assert response_user2_after_publish.status_code == 200, response_user2_after_publish.text

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


def test_create_food_protein_above_100_returns_422(client: TestClient) -> None:
    register_user(client, email="user1@example.com", username="userone")
    token_user1 = login_and_get_token(client, identifier="user1@example.com")

    response = client.post(
        "/foods",
        headers=auth_headers(token_user1),
        json={
            "name": "Too much protein",
            "brand": "Brand",
            "kcal": "250.00",
            "protein": "101.00",
            "fat": "10.00",
            "carbs": "10.00",
        },
    )
    assert response.status_code == 422, response.text


def test_create_food_kcal_above_1000_returns_422(client: TestClient) -> None:
    register_user(client, email="user1@example.com", username="userone")
    token_user1 = login_and_get_token(client, identifier="user1@example.com")

    response = client.post(
        "/foods",
        headers=auth_headers(token_user1),
        json={
            "name": "Too much calories",
            "brand": "Brand",
            "kcal": "1001.00",
            "protein": "20.00",
            "fat": "10.00",
            "carbs": "10.00",
        },
    )
    assert response.status_code == 422, response.text


def test_patch_food_carbs_above_100_returns_422(client: TestClient) -> None:
    register_user(client, email="user1@example.com", username="userone")
    token_user1 = login_and_get_token(client, identifier="user1@example.com")
    created_food = create_food_via_api(client, token_user1)
    food_id = created_food["id"]

    response = client.patch(
        f"/foods/{food_id}",
        headers=auth_headers(token_user1),
        json={"carbs": "150"},
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


def test_serving_grams_validation(client: TestClient) -> None:
    register_user(client, email="user1@example.com", username="userone")
    token_user1 = login_and_get_token(client, identifier="user1@example.com")
    created_food = create_food_via_api(client, token_user1)
    food_id = created_food["id"]

    grams_zero = client.post(
        f"/foods/{food_id}/servings",
        headers=auth_headers(token_user1),
        json={"name": "Zero", "grams": "0"},
    )
    assert grams_zero.status_code == 422, grams_zero.text

    grams_negative = client.post(
        f"/foods/{food_id}/servings",
        headers=auth_headers(token_user1),
        json={"name": "Negative", "grams": "-1"},
    )
    assert grams_negative.status_code == 422, grams_negative.text


def test_other_user_cannot_delete_serving_returns_404(client: TestClient) -> None:
    register_user(client, email="user1@example.com", username="userone")
    register_user(client, email="user2@example.com", username="usertwo")
    token_user1 = login_and_get_token(client, identifier="user1@example.com")
    token_user2 = login_and_get_token(client, identifier="user2@example.com")

    created_food = create_food_via_api(client, token_user1)
    food_id = created_food["id"]
    serving = create_serving_via_api(client, token_user1, food_id)

    delete_response = client.delete(f"/servings/{serving['id']}", headers=auth_headers(token_user2))
    assert delete_response.status_code == 404, delete_response.text


def test_list_servings_requires_food_visibility(client: TestClient) -> None:
    register_user(client, email="user1@example.com", username="userone")
    register_user(client, email="user2@example.com", username="usertwo")
    token_user1 = login_and_get_token(client, identifier="user1@example.com")
    token_user2 = login_and_get_token(client, identifier="user2@example.com")

    created_food = create_food_via_api(client, token_user1)
    food_id = created_food["id"]
    serving = create_serving_via_api(client, token_user1, food_id, name="1 piece", grams="120")

    owner_list = client.get(f"/foods/{food_id}/servings", headers=auth_headers(token_user1))
    assert owner_list.status_code == 200, owner_list.text
    owner_ids = [item["id"] for item in owner_list.json()]
    assert serving["id"] in owner_ids

    other_list = client.get(f"/foods/{food_id}/servings", headers=auth_headers(token_user2))
    assert other_list.status_code == 404, other_list.text


def test_happy_path_create_list_delete_serving(client: TestClient) -> None:
    register_user(client, email="user1@example.com", username="userone")
    token_user1 = login_and_get_token(client, identifier="user1@example.com")

    created_food = create_food_via_api(client, token_user1)
    food_id = created_food["id"]

    created_serving = create_serving_via_api(client, token_user1, food_id, name="1 glass", grams="200")

    list_after_create = client.get(f"/foods/{food_id}/servings", headers=auth_headers(token_user1))
    assert list_after_create.status_code == 200, list_after_create.text
    ids_after_create = [item["id"] for item in list_after_create.json()]
    assert created_serving["id"] in ids_after_create

    delete_response = client.delete(f"/servings/{created_serving['id']}", headers=auth_headers(token_user1))
    assert delete_response.status_code == 204, delete_response.text

    list_after_delete = client.get(f"/foods/{food_id}/servings", headers=auth_headers(token_user1))
    assert list_after_delete.status_code == 200, list_after_delete.text
    assert list_after_delete.json() == []


def test_reports_unlist_on_threshold(client: TestClient) -> None:
    register_user(client, email="owner@example.com", username="owneruser")
    register_user(client, email="u1@example.com", username="userone")
    register_user(client, email="u2@example.com", username="usertwo")
    register_user(client, email="u3@example.com", username="userthree")

    owner_token = login_and_get_token(client, identifier="owner@example.com")
    user1_token = login_and_get_token(client, identifier="u1@example.com")
    user2_token = login_and_get_token(client, identifier="u2@example.com")
    user3_token = login_and_get_token(client, identifier="u3@example.com")

    created_food = create_food_via_api(client, owner_token, name="Community Bread")
    food_id = created_food["id"]
    created_serving = create_serving_via_api(client, owner_token, food_id, name="1 slice", grams="30")

    publish_response = client.post(f"/foods/{food_id}/publish", headers=auth_headers(owner_token))
    assert publish_response.status_code == 200, publish_response.text
    assert publish_response.json()["status"] == "approved"

    for token in (user1_token, user2_token, user3_token):
        report_response = client.post(
            f"/foods/{food_id}/reports",
            headers=auth_headers(token),
            json={"reason": "bad data"},
        )
        assert report_response.status_code == 200, report_response.text

    assert report_response.json()["status"] == "pending"
    assert report_response.json()["is_listed"] is False

    foreign_get = client.get(f"/foods/{food_id}", headers=auth_headers(user1_token))
    assert foreign_get.status_code == 200, foreign_get.text
    assert foreign_get.json()["status"] == "pending"

    foreign_search = client.get(
        "/foods/search",
        headers=auth_headers(user1_token),
        params={"q": "Community"},
    )
    assert foreign_search.status_code == 200, foreign_search.text
    assert all(item["id"] != food_id for item in foreign_search.json())

    foreign_servings = client.get(f"/foods/{food_id}/servings", headers=auth_headers(user1_token))
    assert foreign_servings.status_code == 200, foreign_servings.text
    assert any(item["id"] == created_serving["id"] for item in foreign_servings.json())

    owner_get = client.get(f"/foods/{food_id}", headers=auth_headers(owner_token))
    assert owner_get.status_code == 200, owner_get.text
    assert owner_get.json()["status"] == "pending"
    assert owner_get.json()["is_listed"] is False


def test_withdraw_unlists_but_keeps_access_by_id(client: TestClient) -> None:
    register_user(client, email="owner@example.com", username="owneruser")
    register_user(client, email="u1@example.com", username="userone")

    owner_token = login_and_get_token(client, identifier="owner@example.com")
    user1_token = login_and_get_token(client, identifier="u1@example.com")

    created_food = create_food_via_api(client, owner_token, name="Community Tuna")
    food_id = created_food["id"]

    publish_response = client.post(f"/foods/{food_id}/publish", headers=auth_headers(owner_token))
    assert publish_response.status_code == 200, publish_response.text

    withdraw_response = client.post(f"/foods/{food_id}/withdraw", headers=auth_headers(owner_token))
    assert withdraw_response.status_code == 200, withdraw_response.text
    withdrawn_food = withdraw_response.json()
    assert withdrawn_food["source"] == "community"
    assert withdrawn_food["status"] == "approved"
    assert withdrawn_food["is_listed"] is False

    search_other = client.get(
        "/foods/search",
        headers=auth_headers(user1_token),
        params={"q": "Community"},
    )
    assert search_other.status_code == 200, search_other.text
    assert all(item["id"] != food_id for item in search_other.json())

    search_owner = client.get(
        "/foods/search",
        headers=auth_headers(owner_token),
        params={"q": "Community"},
    )
    assert search_owner.status_code == 200, search_owner.text
    assert any(item["id"] == food_id for item in search_owner.json())

    get_other = client.get(f"/foods/{food_id}", headers=auth_headers(user1_token))
    assert get_other.status_code == 200, get_other.text
    assert get_other.json()["id"] == food_id

    get_owner = client.get(f"/foods/{food_id}", headers=auth_headers(owner_token))
    assert get_owner.status_code == 200, get_owner.text
    assert get_owner.json()["id"] == food_id


def test_withdraw_by_non_owner_returns_403(client: TestClient) -> None:
    register_user(client, email="owner@example.com", username="owneruser")
    register_user(client, email="u1@example.com", username="userone")

    owner_token = login_and_get_token(client, identifier="owner@example.com")
    user1_token = login_and_get_token(client, identifier="u1@example.com")

    created_food = create_food_via_api(client, owner_token, name="Community Rice")
    food_id = created_food["id"]
    publish_response = client.post(f"/foods/{food_id}/publish", headers=auth_headers(owner_token))
    assert publish_response.status_code == 200, publish_response.text

    withdraw_response = client.post(f"/foods/{food_id}/withdraw", headers=auth_headers(user1_token))
    assert withdraw_response.status_code == 403, withdraw_response.text


def test_withdraw_twice_returns_409(client: TestClient) -> None:
    register_user(client, email="owner@example.com", username="owneruser")
    owner_token = login_and_get_token(client, identifier="owner@example.com")

    created_food = create_food_via_api(client, owner_token, name="Community Oats")
    food_id = created_food["id"]
    publish_response = client.post(f"/foods/{food_id}/publish", headers=auth_headers(owner_token))
    assert publish_response.status_code == 200, publish_response.text

    first_withdraw = client.post(f"/foods/{food_id}/withdraw", headers=auth_headers(owner_token))
    assert first_withdraw.status_code == 200, first_withdraw.text

    second_withdraw = client.post(f"/foods/{food_id}/withdraw", headers=auth_headers(owner_token))
    assert second_withdraw.status_code == 409, second_withdraw.text


def test_duplicate_report_by_same_user_returns_409(client: TestClient) -> None:
    register_user(client, email="owner@example.com", username="owneruser")
    register_user(client, email="u1@example.com", username="userone")

    owner_token = login_and_get_token(client, identifier="owner@example.com")
    user1_token = login_and_get_token(client, identifier="u1@example.com")

    created_food = create_food_via_api(client, owner_token, name="Community Milk")
    food_id = created_food["id"]

    publish_response = client.post(f"/foods/{food_id}/publish", headers=auth_headers(owner_token))
    assert publish_response.status_code == 200, publish_response.text

    first_report = client.post(
        f"/foods/{food_id}/reports",
        headers=auth_headers(user1_token),
        json={"reason": "wrong macros"},
    )
    assert first_report.status_code == 200, first_report.text

    duplicate_report = client.post(
        f"/foods/{food_id}/reports",
        headers=auth_headers(user1_token),
        json={"reason": "duplicate"},
    )
    assert duplicate_report.status_code == 409, duplicate_report.text


def test_cannot_report_own_food(client: TestClient) -> None:
    register_user(client, email="owner@example.com", username="owneruser")
    owner_token = login_and_get_token(client, identifier="owner@example.com")

    created_food = create_food_via_api(client, owner_token, name="Community Pasta")
    food_id = created_food["id"]

    publish_response = client.post(f"/foods/{food_id}/publish", headers=auth_headers(owner_token))
    assert publish_response.status_code == 200, publish_response.text

    report_response = client.post(
        f"/foods/{food_id}/reports",
        headers=auth_headers(owner_token),
        json={"reason": "self report"},
    )
    assert report_response.status_code == 400, report_response.text


def test_admin_moderate_approve_reject(client: TestClient, db_session_factory: sessionmaker[Session]) -> None:
    register_user(client, email="owner@example.com", username="owneruser")
    register_user(client, email="u1@example.com", username="userone")
    register_user(client, email="u2@example.com", username="usertwo")
    register_user(client, email="u3@example.com", username="userthree")
    create_admin_user(db_session_factory)

    owner_token = login_and_get_token(client, identifier="owner@example.com")
    user1_token = login_and_get_token(client, identifier="u1@example.com")
    user2_token = login_and_get_token(client, identifier="u2@example.com")
    user3_token = login_and_get_token(client, identifier="u3@example.com")
    admin_token = login_and_get_token(client, identifier="admin@example.com")

    created_food = create_food_via_api(client, owner_token, name="Community Soup")
    food_id = created_food["id"]

    publish_response = client.post(f"/foods/{food_id}/publish", headers=auth_headers(owner_token))
    assert publish_response.status_code == 200, publish_response.text

    for token in (user1_token, user2_token, user3_token):
        report_response = client.post(
            f"/foods/{food_id}/reports",
            headers=auth_headers(token),
            json={"reason": "needs moderation"},
        )
        assert report_response.status_code == 200, report_response.text
    assert report_response.json()["status"] == "pending"

    approve_response = client.put(
        f"/admin/foods/{food_id}/moderate",
        headers=auth_headers(admin_token),
        params={"action": "approve"},
    )
    assert approve_response.status_code == 200, approve_response.text
    assert approve_response.json()["status"] == "approved"

    reject_response = client.put(
        f"/admin/foods/{food_id}/moderate",
        headers=auth_headers(admin_token),
        params={"action": "reject"},
    )
    assert reject_response.status_code == 200, reject_response.text
    assert reject_response.json()["status"] == "rejected"
