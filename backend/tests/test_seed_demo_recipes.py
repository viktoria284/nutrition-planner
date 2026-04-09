from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.models.enums import FoodSource, FoodStatus
from app.models.recipe import Recipe
from app.services.recipes import DEMO_MEAL_TYPES, DEMO_PUBLIC_RECIPES, seed_demo_public_recipes


def test_seed_demo_recipes_is_idempotent(
    db_session_factory: sessionmaker[Session],
) -> None:
    db = db_session_factory()
    try:
        first_stats = seed_demo_public_recipes(db)
        assert first_stats["created_recipes"] == first_stats["total_demo_recipes"]

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
        assert stats["total_demo_recipes"] >= 10
        assert all(stats[meal_type] > 0 for meal_type in DEMO_MEAL_TYPES)

        demo_names = [item["name"] for item in DEMO_PUBLIC_RECIPES]
        demo_recipes = db.execute(
            select(Recipe).where(Recipe.name.in_(demo_names))
        ).scalars().all()

        covered = set()
        for recipe in demo_recipes:
            covered.update(recipe.meal_types)
        assert all(meal_type in covered for meal_type in DEMO_MEAL_TYPES)
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
