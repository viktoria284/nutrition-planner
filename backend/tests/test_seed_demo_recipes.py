from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.models.enums import FoodSource, FoodStatus
from app.models.recipe import Recipe
from app.models.user import User
from app.services.media import get_recipes_upload_dir
from app.services.recipes import (
    DEMO_MEAL_TYPES,
    DEMO_PUBLIC_RECIPES,
    list_accessible_recipes,
    seed_demo_public_recipes,
)


MIN_DEMO_RECIPES = 72
MAX_DEMO_RECIPES = len(DEMO_PUBLIC_RECIPES)
MIN_MEAL_TYPE_COUNTS = {
    "breakfast": 25,
    "lunch": 28,
    "dinner": 28,
    "snack": 18,
}
HIGH_CALORIE_CARB_FAT_FRIENDLY_RECIPES = {
    "Овсянка с арахисовой пастой и бананом",
    "Тосты с творогом и бананом",
    "Паста с говядиной и оливковым маслом",
    "Рис с лососем и оливковым маслом",
    "Курица с пастой и оливковым маслом",
    "Говядина с рисом и подсолнечным маслом",
    "Йогурт с бананом и арахисовой пастой",
    "Тосты с арахисовой пастой и грушей",
}


def test_seed_demo_recipes_is_idempotent(
    db_session_factory: sessionmaker[Session],
) -> None:
    db = db_session_factory()
    try:
        first_stats = seed_demo_public_recipes(db)
        assert first_stats["created_recipes"] == first_stats["total_demo_recipes"]
        assert MIN_DEMO_RECIPES <= first_stats["total_demo_recipes"] <= MAX_DEMO_RECIPES

        second_stats = seed_demo_public_recipes(db)
        assert second_stats["created_recipes"] == 0
        assert second_stats["skipped_recipes"] == second_stats["total_demo_recipes"]

        demo_names = [item["name"] for item in DEMO_PUBLIC_RECIPES]
        demo_recipes = db.execute(
            select(Recipe).where(Recipe.name.in_(demo_names))
        ).scalars().all()
        assert len(demo_recipes) == len(DEMO_PUBLIC_RECIPES)
        assert all(recipe.source == FoodSource.community for recipe in demo_recipes)
        assert all(recipe.status == FoodStatus.approved for recipe in demo_recipes)
        assert all(recipe.is_listed is True for recipe in demo_recipes)

        duplicate_count = db.execute(
            select(func.count(Recipe.id)).where(Recipe.name.in_(demo_names))
        ).scalar_one()
        assert int(duplicate_count or 0) == len(DEMO_PUBLIC_RECIPES)
    finally:
        db.close()


def test_seed_demo_recipes_have_meal_type_coverage(
    db_session_factory: sessionmaker[Session],
) -> None:
    db = db_session_factory()
    try:
        stats = seed_demo_public_recipes(db, replace_demo=True)
        assert MIN_DEMO_RECIPES <= stats["total_demo_recipes"] <= MAX_DEMO_RECIPES
        assert all(stats[meal_type] >= MIN_MEAL_TYPE_COUNTS[meal_type] for meal_type in DEMO_MEAL_TYPES)

        demo_names = [item["name"] for item in DEMO_PUBLIC_RECIPES]
        demo_recipes = db.execute(
            select(Recipe).where(Recipe.name.in_(demo_names))
        ).scalars().all()

        covered = set()
        for recipe in demo_recipes:
            covered.update(recipe.meal_types)
        assert all(meal_type in covered for meal_type in DEMO_MEAL_TYPES)
        assert len(demo_recipes) >= MIN_DEMO_RECIPES
    finally:
        db.close()


def test_seed_creates_public_breakfast_recipes(
    db_session_factory: sessionmaker[Session],
) -> None:
    db = db_session_factory()
    try:
        seed_demo_public_recipes(db, replace_demo=True)
        recipes = db.execute(
            select(Recipe).where(
                Recipe.source == FoodSource.community,
                Recipe.status == FoodStatus.approved,
                Recipe.is_listed.is_(True),
            )
        ).scalars().all()
        assert any("breakfast" in recipe.meal_types for recipe in recipes)
    finally:
        db.close()


def test_seed_creates_public_lunch_recipes(
    db_session_factory: sessionmaker[Session],
) -> None:
    db = db_session_factory()
    try:
        seed_demo_public_recipes(db, replace_demo=True)
        recipes = db.execute(
            select(Recipe).where(
                Recipe.source == FoodSource.community,
                Recipe.status == FoodStatus.approved,
                Recipe.is_listed.is_(True),
            )
        ).scalars().all()
        assert any("lunch" in recipe.meal_types for recipe in recipes)
    finally:
        db.close()


def test_seed_creates_universal_lunch_dinner_recipes(
    db_session_factory: sessionmaker[Session],
) -> None:
    db = db_session_factory()
    try:
        seed_demo_public_recipes(db, replace_demo=True)
        demo_names = [item["name"] for item in DEMO_PUBLIC_RECIPES]
        demo_recipes = db.execute(
            select(Recipe).where(Recipe.name.in_(demo_names))
        ).scalars().all()
        universal = [
            recipe for recipe in demo_recipes
            if "lunch" in recipe.meal_types and "dinner" in recipe.meal_types
        ]
        assert len(universal) >= 8
    finally:
        db.close()


def test_seed_demo_recipes_have_cook_time_minutes_by_meal_type(
    db_session_factory: sessionmaker[Session],
) -> None:
    db = db_session_factory()
    try:
        seed_demo_public_recipes(db, replace_demo=True)
        demo_names = [item["name"] for item in DEMO_PUBLIC_RECIPES]
        demo_recipes = db.execute(
            select(Recipe).where(Recipe.name.in_(demo_names))
        ).scalars().all()

        assert len(demo_recipes) == len(DEMO_PUBLIC_RECIPES)
        assert all(recipe.cook_time_minutes is not None for recipe in demo_recipes)
        assert all(recipe.instructions is not None for recipe in demo_recipes)
        assert all(str(recipe.instructions).strip() for recipe in demo_recipes)
        fast_breakfast_count = 0
        fast_lunch_count = 0
        fast_dinner_count = 0
        fast_lunch_dinner_count = 0
        for recipe in demo_recipes:
            meal_types = set(recipe.meal_types)
            assert recipe.cook_time_minutes is not None
            if meal_types & {"breakfast", "snack"}:
                assert 5 <= recipe.cook_time_minutes <= 20
            elif meal_types & {"lunch", "dinner"}:
                assert 10 <= recipe.cook_time_minutes <= 60
            if "breakfast" in meal_types and recipe.cook_time_minutes <= 15:
                fast_breakfast_count += 1
            if "lunch" in meal_types and recipe.cook_time_minutes <= 25:
                fast_lunch_count += 1
            if "dinner" in meal_types and recipe.cook_time_minutes <= 25:
                fast_dinner_count += 1
            if {"lunch", "dinner"}.issubset(meal_types) and recipe.cook_time_minutes <= 25:
                fast_lunch_dinner_count += 1

        assert fast_breakfast_count >= 12
        assert fast_lunch_count >= 16
        assert fast_dinner_count >= 16
        assert fast_lunch_dinner_count >= 12
    finally:
        db.close()


def test_seed_demo_recipes_have_demo_cover_images(
    db_session_factory: sessionmaker[Session],
) -> None:
    db = db_session_factory()
    try:
        seed_demo_public_recipes(db, replace_demo=True)
        demo_names = [item["name"] for item in DEMO_PUBLIC_RECIPES]
        demo_recipes = db.execute(
            select(Recipe).where(Recipe.name.in_(demo_names))
        ).scalars().all()
        assert len(demo_recipes) == len(DEMO_PUBLIC_RECIPES)
        assert all(recipe.image_url for recipe in demo_recipes)
        assert all(str(recipe.image_url).startswith("/media/recipes/demo/") for recipe in demo_recipes)

        recipes_upload_dir = get_recipes_upload_dir()
        for recipe in demo_recipes:
            assert recipe.image_url is not None
            relative_path = recipe.image_url.removeprefix("/media/recipes/")
            image_path = recipes_upload_dir / relative_path
            assert image_path.exists()
            assert image_path.is_file()
            assert image_path.suffix == ".svg"
    finally:
        db.close()


def test_seed_demo_recipes_recreates_missing_demo_cover_images(
    db_session_factory: sessionmaker[Session],
) -> None:
    db = db_session_factory()
    try:
        seed_demo_public_recipes(db, replace_demo=True)
        demo_recipe = db.execute(
            select(Recipe).where(
                Recipe.source == FoodSource.community,
                Recipe.status == FoodStatus.approved,
                Recipe.is_listed.is_(True),
            )
        ).scalars().first()
        assert demo_recipe is not None
        assert demo_recipe.image_url is not None

        recipes_upload_dir = get_recipes_upload_dir()
        relative_path = demo_recipe.image_url.removeprefix("/media/recipes/")
        image_path = recipes_upload_dir / relative_path
        assert image_path.exists()
        image_path.unlink(missing_ok=True)
        assert not image_path.exists()

        stats = seed_demo_public_recipes(db)
        assert stats["generated_demo_images"] >= 1
        assert image_path.exists()
    finally:
        db.close()


def test_seed_demo_cover_images_do_not_contain_demo_label(
    db_session_factory: sessionmaker[Session],
) -> None:
    db = db_session_factory()
    try:
        seed_demo_public_recipes(db, replace_demo=True)
        demo_recipe = db.execute(
            select(Recipe).where(
                Recipe.source == FoodSource.community,
                Recipe.status == FoodStatus.approved,
                Recipe.is_listed.is_(True),
                Recipe.image_url.is_not(None),
            )
        ).scalars().first()
        assert demo_recipe is not None
        assert demo_recipe.image_url is not None

        recipes_upload_dir = get_recipes_upload_dir()
        image_path = recipes_upload_dir / demo_recipe.image_url.removeprefix("/media/recipes/")
        assert image_path.exists()
        content = image_path.read_text(encoding="utf-8").lower()
        assert "demo recipe" not in content
        assert "демо рецепт" not in content
    finally:
        db.close()


def test_seed_demo_recipes_include_high_calorie_carb_fat_friendly_options(
    db_session_factory: sessionmaker[Session],
) -> None:
    db = db_session_factory()
    try:
        seed_demo_public_recipes(db, replace_demo=True)
        demo_names = {item["name"] for item in DEMO_PUBLIC_RECIPES}
        assert HIGH_CALORIE_CARB_FAT_FRIENDLY_RECIPES.issubset(demo_names)

        seeded = db.execute(
            select(Recipe).where(Recipe.name.in_(sorted(HIGH_CALORIE_CARB_FAT_FRIENDLY_RECIPES)))
        ).scalars().all()
        assert len(seeded) == len(HIGH_CALORIE_CARB_FAT_FRIENDLY_RECIPES)
        assert all(recipe.source == FoodSource.community for recipe in seeded)
        assert all(recipe.status == FoodStatus.approved for recipe in seeded)
        assert all(recipe.is_listed is True for recipe in seeded)
    finally:
        db.close()


def test_seed_demo_recipes_replace_demo_removes_legacy_demo_prefix(
    db_session_factory: sessionmaker[Session],
) -> None:
    db = db_session_factory()
    try:
        seed_demo_public_recipes(db, replace_demo=True)
        demo_names = [item["name"] for item in DEMO_PUBLIC_RECIPES]
        current_demo_recipes = db.execute(
            select(Recipe).where(Recipe.name.in_(demo_names))
        ).scalars().all()
        for recipe in current_demo_recipes:
            recipe.name = f"Demo: {recipe.name}"
        db.commit()

        stats = seed_demo_public_recipes(db, replace_demo=True)
        assert stats["created_recipes"] == stats["total_demo_recipes"]

        all_recipe_names = {
            recipe_name
            for recipe_name in db.execute(select(Recipe.name)).scalars().all()
        }
        assert any(name in all_recipe_names for name in demo_names)
        assert not any(name.startswith("Demo: ") for name in all_recipe_names)
    finally:
        db.close()


def test_seeded_demo_recipes_visible_in_public_catalog(
    db_session_factory: sessionmaker[Session],
) -> None:
    db = db_session_factory()
    try:
        seed_demo_public_recipes(db, replace_demo=True)
        viewer = User(
            email="demo-viewer@example.com",
            username="demo_viewer",
            display_name="Demo Viewer",
            hashed_password="hash",
        )
        db.add(viewer)
        db.commit()
        db.refresh(viewer)

        visible = list_accessible_recipes(
            db,
            user_id=viewer.id,
            include_public=True,
            limit=200,
            offset=0,
            include_ingredients=False,
        )
        demo_names = {item["name"] for item in DEMO_PUBLIC_RECIPES}
        visible_demo = [recipe for recipe in visible if recipe.name in demo_names]
        assert len(visible_demo) >= MIN_DEMO_RECIPES
        assert all(recipe.source == FoodSource.community for recipe in visible_demo)
        assert all(recipe.status == FoodStatus.approved for recipe in visible_demo)
        assert all(recipe.is_listed is True for recipe in visible_demo)
    finally:
        db.close()


def test_seed_demo_recipes_after_verified_foods_seed(
    db_session_factory: sessionmaker[Session],
) -> None:
    db = db_session_factory()
    try:
        from app.services.foods import seed_verified_foods

        created_verified = seed_verified_foods(db, replace_existing_values=True)
        assert created_verified >= 0

        stats = seed_demo_public_recipes(db, replace_demo=True)
        assert stats["created_verified_foods"] == 0
        assert stats["created_recipes"] == stats["total_demo_recipes"]
        assert stats["breakfast"] >= MIN_MEAL_TYPE_COUNTS["breakfast"]
        assert stats["lunch"] >= MIN_MEAL_TYPE_COUNTS["lunch"]
        assert stats["dinner"] >= MIN_MEAL_TYPE_COUNTS["dinner"]
        assert stats["snack"] >= MIN_MEAL_TYPE_COUNTS["snack"]
    finally:
        db.close()
