from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from test_plans_api import (
    add_ingredient_via_api,
    auth_headers,
    create_food_via_api,
    create_plan_via_api,
    create_recipe_via_api,
    create_user_with_token,
)


def _create_profile(
    client: TestClient,
    token: str,
    *,
    name: str,
    kcal: int | None,
    protein: int | None,
    fat: int | None,
    carbs: int | None,
    fiber: int | None,
) -> dict:
    response = client.post(
        "/profiles",
        headers=auth_headers(token),
        json={
            "name": name,
            "target_kcal": kcal,
            "target_protein": protein,
            "target_fat": fat,
            "target_carbs": carbs,
            "target_fiber": fiber,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _patch_profile(client: TestClient, token: str, profile_id: int, payload: dict) -> dict:
    response = client.patch(f"/profiles/{profile_id}", headers=auth_headers(token), json=payload)
    assert response.status_code == 200, response.text
    return response.json()


def _create_recipe_with_food(
    client: TestClient,
    token: str,
    *,
    food_payload: dict,
    recipe_name: str = "Analytics recipe",
    meal_types: list[str] | None = None,
    grams: str = "100",
) -> tuple[dict, dict, dict]:
    food = create_food_via_api(client, token, **food_payload)
    recipe = create_recipe_via_api(client, token, name=recipe_name, servings_count=1, meal_types=meal_types or ["lunch"])
    ingredient = add_ingredient_via_api(
        client,
        token,
        recipe_id=recipe["id"],
        food_id=food["id"],
        grams=grams,
    )
    return food, recipe, ingredient


def _assign_recipe_to_slots(
    client: TestClient,
    token: str,
    *,
    plan: dict,
    slot_index: int,
    recipe_id: int,
    multipliers_by_date: dict[str, str] | None = None,
) -> None:
    multipliers_by_date = multipliers_by_date or {}
    for slot in plan["slots"]:
        if slot["slot_index"] != slot_index:
            continue
        multiplier = multipliers_by_date.get(slot["day_date"], "1")
        patch = client.patch(
            f"/plans/{plan['id']}/slots/{slot['id']}",
            headers=auth_headers(token),
            json={"recipe_id": recipe_id, "servings_multiplier": multiplier},
        )
        assert patch.status_code == 200, patch.text


def _get_analytics(client: TestClient, token: str, plan_id: int) -> dict:
    response = client.get(f"/plans/{plan_id}/analytics", headers=auth_headers(token))
    assert response.status_code == 200, response.text
    return response.json()


def test_owner_can_get_plan_analytics(client: TestClient, db_session_factory: sessionmaker[Session]) -> None:
    _user, token = create_user_with_token(db_session_factory, email="analytics_owner@example.com", username="analytics_owner")
    profile = _create_profile(client, token, name="A", kcal=100, protein=10, fat=5, carbs=20, fiber=4)
    _food, recipe, _ingredient = _create_recipe_with_food(
        client,
        token,
        food_payload={"name": "Analytics food", "kcal": "100", "protein": "10", "fat": "5", "carbs": "20", "fiber": "4"},
    )
    plan = create_plan_via_api(client, token, days_count=2, meals_per_day=2, profile_id=profile["id"])
    _assign_recipe_to_slots(client, token, plan=plan, slot_index=0, recipe_id=recipe["id"])

    analytics = _get_analytics(client, token, plan["id"])
    assert analytics["period_summary"]["days_count"] == 2
    assert analytics["targets"]["kcal"] == 100


def test_other_user_gets_404_for_plan_analytics(client: TestClient, db_session_factory: sessionmaker[Session]) -> None:
    _owner, owner_token = create_user_with_token(db_session_factory, email="analytics_own@example.com", username="analytics_own")
    _other, other_token = create_user_with_token(db_session_factory, email="analytics_other@example.com", username="analytics_other")

    profile = _create_profile(client, owner_token, name="B", kcal=100, protein=10, fat=5, carbs=20, fiber=4)
    plan = create_plan_via_api(client, owner_token, days_count=1, meals_per_day=2, profile_id=profile["id"])

    response = client.get(f"/plans/{plan['id']}/analytics", headers=auth_headers(other_token))
    assert response.status_code == 404, response.text


def test_analytics_uses_plan_snapshot_not_active_profile(client: TestClient, db_session_factory: sessionmaker[Session]) -> None:
    _user, token = create_user_with_token(db_session_factory, email="analytics_snapshot@example.com", username="analytics_snapshot")
    profile = _create_profile(client, token, name="Snapshot", kcal=1800, protein=100, fat=70, carbs=200, fiber=25)
    plan = create_plan_via_api(client, token, days_count=1, meals_per_day=2, profile_id=profile["id"])

    _patch_profile(client, token, profile["id"], {"target_kcal": 2600, "target_protein": 140})

    analytics = _get_analytics(client, token, plan["id"])
    assert analytics["targets"]["kcal"] == 1800
    assert analytics["targets"]["protein"] == 100


def test_average_totals_and_percent_values_are_correct(client: TestClient, db_session_factory: sessionmaker[Session]) -> None:
    _user, token = create_user_with_token(db_session_factory, email="analytics_avg@example.com", username="analytics_avg")
    profile = _create_profile(client, token, name="Avg", kcal=100, protein=10, fat=5, carbs=20, fiber=4)
    _food, recipe, _ingredient = _create_recipe_with_food(
        client,
        token,
        food_payload={"name": "Avg food", "kcal": "100", "protein": "10", "fat": "5", "carbs": "20", "fiber": "4"},
    )
    plan = create_plan_via_api(client, token, days_count=2, meals_per_day=2, profile_id=profile["id"])
    _assign_recipe_to_slots(client, token, plan=plan, slot_index=0, recipe_id=recipe["id"])

    analytics = _get_analytics(client, token, plan["id"])
    period = analytics["period_summary"]

    assert Decimal(str(period["average_kcal"])) == Decimal("100.00")
    assert Decimal(str(period["average_protein"])) == Decimal("10.00")
    assert Decimal(str(period["average_fat"])) == Decimal("5.00")
    assert Decimal(str(period["average_carbs"])) == Decimal("20.00")
    assert Decimal(str(period["average_fiber"])) == Decimal("4.00")
    assert Decimal(str(period["kcal_percent"])) == Decimal("100.0")
    assert Decimal(str(period["protein_percent"])) == Decimal("100.0")
    assert Decimal(str(period["fat_percent"])) == Decimal("100.0")
    assert Decimal(str(period["carbs_percent"])) == Decimal("100.0")
    assert Decimal(str(period["fiber_percent"])) == Decimal("100.0")


def test_analytics_period_averages_match_plan_day_totals(client: TestClient, db_session_factory: sessionmaker[Session]) -> None:
    _user, token = create_user_with_token(db_session_factory, email="analytics_match_totals@example.com", username="analytics_match_totals")
    profile = _create_profile(client, token, name="Match", kcal=2000, protein=100, fat=70, carbs=220, fiber=25)
    _food, recipe, _ingredient = _create_recipe_with_food(
        client,
        token,
        food_payload={"name": "Match food", "kcal": "100", "protein": "10", "fat": "5", "carbs": "20", "fiber": "4"},
    )
    plan = create_plan_via_api(client, token, start_date="2026-05-01", days_count=3, meals_per_day=2, profile_id=profile["id"])
    _assign_recipe_to_slots(
        client,
        token,
        plan=plan,
        slot_index=0,
        recipe_id=recipe["id"],
        multipliers_by_date={
            "2026-05-01": "0.8",
            "2026-05-02": "1",
            "2026-05-03": "1.2",
        },
    )

    plan_response = client.get(f"/plans/{plan['id']}", headers=auth_headers(token))
    assert plan_response.status_code == 200, plan_response.text
    plan_payload = plan_response.json()

    analytics = _get_analytics(client, token, plan["id"])
    period = analytics["period_summary"]

    day_count = Decimal(str(len(plan_payload["days"])))
    total_protein = sum(Decimal(str(day["totals"]["protein"])) for day in plan_payload["days"])
    total_fat = sum(Decimal(str(day["totals"]["fat"])) for day in plan_payload["days"])
    total_carbs = sum(Decimal(str(day["totals"]["carbs"])) for day in plan_payload["days"])
    total_fiber = sum(Decimal(str(day["totals"]["fiber"])) for day in plan_payload["days"])

    expected_average_protein = (total_protein / day_count).quantize(Decimal("0.01"))
    expected_average_fat = (total_fat / day_count).quantize(Decimal("0.01"))
    expected_average_carbs = (total_carbs / day_count).quantize(Decimal("0.01"))
    expected_average_fiber = (total_fiber / day_count).quantize(Decimal("0.01"))

    assert Decimal(str(period["average_protein"])) == expected_average_protein
    assert Decimal(str(period["average_fat"])) == expected_average_fat
    assert Decimal(str(period["average_carbs"])) == expected_average_carbs
    assert Decimal(str(period["average_fiber"])) == expected_average_fiber

    expected_protein_percent = ((expected_average_protein / Decimal(str(profile["target_protein"]))) * Decimal("100")).quantize(
        Decimal("0.1")
    )
    expected_fat_percent = ((expected_average_fat / Decimal(str(profile["target_fat"]))) * Decimal("100")).quantize(
        Decimal("0.1")
    )
    expected_carbs_percent = ((expected_average_carbs / Decimal(str(profile["target_carbs"]))) * Decimal("100")).quantize(
        Decimal("0.1")
    )
    expected_fiber_percent = ((expected_average_fiber / Decimal(str(profile["target_fiber"]))) * Decimal("100")).quantize(
        Decimal("0.1")
    )

    assert Decimal(str(period["protein_percent"])) == expected_protein_percent
    assert Decimal(str(period["fat_percent"])) == expected_fat_percent
    assert Decimal(str(period["carbs_percent"])) == expected_carbs_percent
    assert Decimal(str(period["fiber_percent"])) == expected_fiber_percent


def test_statuses_for_kcal_and_macros_low_ok_high(client: TestClient, db_session_factory: sessionmaker[Session]) -> None:
    _user, token = create_user_with_token(db_session_factory, email="analytics_status@example.com", username="analytics_status")
    profile = _create_profile(client, token, name="Status", kcal=100, protein=10, fat=5, carbs=20, fiber=4)
    _food, recipe, _ingredient = _create_recipe_with_food(
        client,
        token,
        food_payload={"name": "Status food", "kcal": "100", "protein": "10", "fat": "5", "carbs": "20", "fiber": "4"},
    )
    plan = create_plan_via_api(client, token, start_date="2026-05-01", days_count=3, meals_per_day=2, profile_id=profile["id"])
    _assign_recipe_to_slots(
        client,
        token,
        plan=plan,
        slot_index=0,
        recipe_id=recipe["id"],
        multipliers_by_date={
            "2026-05-01": "0.8",
            "2026-05-02": "1",
            "2026-05-03": "1.2",
        },
    )

    analytics = _get_analytics(client, token, plan["id"])
    by_date = {item["date"]: item for item in analytics["day_analytics"]}

    assert by_date["2026-05-01"]["kcal"]["status"] == "low"
    assert by_date["2026-05-02"]["kcal"]["status"] == "ok"
    assert by_date["2026-05-03"]["kcal"]["status"] == "high"

    assert by_date["2026-05-01"]["protein"]["status"] == "low"
    assert by_date["2026-05-02"]["protein"]["status"] == "ok"
    assert by_date["2026-05-03"]["protein"]["status"] == "high"


def test_fiber_no_target_when_target_fiber_missing(client: TestClient, db_session_factory: sessionmaker[Session]) -> None:
    _user, token = create_user_with_token(db_session_factory, email="analytics_fiber_none@example.com", username="analytics_fiber_none")
    profile = _create_profile(client, token, name="Fiber none", kcal=100, protein=10, fat=5, carbs=20, fiber=None)
    _food, recipe, _ingredient = _create_recipe_with_food(
        client,
        token,
        food_payload={"name": "Fiber none food", "kcal": "100", "protein": "10", "fat": "5", "carbs": "20", "fiber": "8"},
    )
    plan = create_plan_via_api(client, token, days_count=1, meals_per_day=2, profile_id=profile["id"])
    _assign_recipe_to_slots(client, token, plan=plan, slot_index=0, recipe_id=recipe["id"])

    analytics = _get_analytics(client, token, plan["id"])
    day = analytics["day_analytics"][0]
    assert day["fiber"]["status"] == "no_target"
    assert day["fiber"]["percent"] is None


def test_fiber_high_recommendation_is_neutral(client: TestClient, db_session_factory: sessionmaker[Session]) -> None:
    _user, token = create_user_with_token(db_session_factory, email="analytics_fiber_high@example.com", username="analytics_fiber_high")
    profile = _create_profile(client, token, name="Fiber high", kcal=100, protein=10, fat=5, carbs=20, fiber=10)
    _food, recipe, _ingredient = _create_recipe_with_food(
        client,
        token,
        food_payload={"name": "Fiber high food", "kcal": "100", "protein": "10", "fat": "5", "carbs": "20", "fiber": "30"},
    )
    plan = create_plan_via_api(client, token, days_count=1, meals_per_day=2, profile_id=profile["id"])
    _assign_recipe_to_slots(client, token, plan=plan, slot_index=0, recipe_id=recipe["id"])

    analytics = _get_analytics(client, token, plan["id"])
    assert analytics["day_analytics"][0]["fiber"]["status"] == "high"
    joined = " ".join(analytics["recommendations"])
    assert "Клетчатка выше ориентира" in joined


def test_empty_plan_returns_zeros_without_crash(client: TestClient, db_session_factory: sessionmaker[Session]) -> None:
    _user, token = create_user_with_token(db_session_factory, email="analytics_empty@example.com", username="analytics_empty")
    profile = _create_profile(client, token, name="Empty", kcal=1800, protein=100, fat=70, carbs=200, fiber=25)
    plan = create_plan_via_api(client, token, days_count=2, meals_per_day=2, profile_id=profile["id"])

    analytics = _get_analytics(client, token, plan["id"])
    assert analytics["period_summary"]["days_count"] == 2
    assert Decimal(str(analytics["period_summary"]["average_kcal"])) == Decimal("0.00")
    assert len(analytics["day_analytics"]) == 2


def test_missing_targets_returns_friendly_422(client: TestClient, db_session_factory: sessionmaker[Session]) -> None:
    _user, token = create_user_with_token(db_session_factory, email="analytics_notarget@example.com", username="analytics_notarget")
    profile = _create_profile(client, token, name="No targets", kcal=None, protein=None, fat=None, carbs=None, fiber=None)
    plan = create_plan_via_api(client, token, days_count=1, meals_per_day=2, profile_id=profile["id"])

    response = client.get(f"/plans/{plan['id']}/analytics", headers=auth_headers(token))
    assert response.status_code == 422, response.text
    assert response.json()["detail"] == "Для оценки плана нужны цели профиля."


def test_slot_ingredient_overrides_affect_analytics(client: TestClient, db_session_factory: sessionmaker[Session]) -> None:
    _user, token = create_user_with_token(db_session_factory, email="analytics_override@example.com", username="analytics_override")
    profile = _create_profile(client, token, name="Overrides", kcal=100, protein=10, fat=5, carbs=20, fiber=4)
    food, recipe, ingredient = _create_recipe_with_food(
        client,
        token,
        food_payload={"name": "Override food", "kcal": "100", "protein": "10", "fat": "5", "carbs": "20", "fiber": "4"},
        grams="200",
    )
    plan = create_plan_via_api(client, token, days_count=1, meals_per_day=2, profile_id=profile["id"])
    _assign_recipe_to_slots(client, token, plan=plan, slot_index=0, recipe_id=recipe["id"])

    before = _get_analytics(client, token, plan["id"])
    before_kcal = Decimal(str(before["day_analytics"][0]["kcal"]["total"]))
    assert before_kcal == Decimal("200.00")

    slot = next(item for item in plan["slots"] if item["slot_index"] == 0)
    override_response = client.put(
        f"/plans/{plan['id']}/slots/{slot['id']}/ingredient-overrides",
        headers=auth_headers(token),
        json={
            "base_overrides": [
                {
                    "recipe_ingredient_id": ingredient["id"],
                    "food_id": food["id"],
                    "grams": "100",
                    "is_excluded": False,
                }
            ],
            "manual_items": [],
        },
    )
    assert override_response.status_code == 200, override_response.text

    after = _get_analytics(client, token, plan["id"])
    after_kcal = Decimal(str(after["day_analytics"][0]["kcal"]["total"]))
    assert after_kcal == Decimal("100.00")
