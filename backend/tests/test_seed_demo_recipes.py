from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.models.enums import FoodSource, FoodStatus
from app.models.recipe import Recipe
from app.models.user import User
from app.services.recipes import (
    DEMO_MEAL_TYPES,
    DEMO_PUBLIC_RECIPES,
    list_accessible_recipes,
    seed_demo_public_recipes,
)


MIN_DEMO_RECIPES = 36
MAX_DEMO_RECIPES = 48
MIN_MEAL_TYPE_COUNTS = {
    "breakfast": 9,
    "lunch": 9,
    "dinner": 9,
    "snack": 6,
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
