"""add eggs food category

Revision ID: c2e8f1a9b4d6
Revises: 6d5f8a7c9b01
Create Date: 2026-05-12 12:00:00.000000

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "c2e8f1a9b4d6"
down_revision: Union[str, None] = "6d5f8a7c9b01"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

FOOD_CATEGORIES_WITH_EGGS = (
    "vegetables",
    "fruits",
    "dairy",
    "eggs",
    "meat_fish",
    "grains_bakery",
    "pantry_spices",
    "nuts_oils",
    "drinks",
    "sweets",
    "frozen",
    "other",
)

FOOD_CATEGORIES_WITHOUT_EGGS = tuple(value for value in FOOD_CATEGORIES_WITH_EGGS if value != "eggs")


def _category_values(categories: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in categories)


def upgrade() -> None:
    op.drop_constraint("ck_shopping_list_items_category_allowed", "shopping_list_items", type_="check")
    op.drop_constraint("ck_food_items_category_allowed", "food_items", type_="check")

    op.execute(
        """
        UPDATE food_items
        SET category = 'eggs'
        WHERE lower(name) LIKE '%яйц%'
        """
    )
    op.execute(
        """
        UPDATE shopping_list_items
        SET category = 'eggs'
        WHERE lower(name_snapshot) LIKE '%яйц%'
        """
    )

    op.create_check_constraint(
        "ck_food_items_category_allowed",
        "food_items",
        f"category IN ({_category_values(FOOD_CATEGORIES_WITH_EGGS)})",
    )
    op.create_check_constraint(
        "ck_shopping_list_items_category_allowed",
        "shopping_list_items",
        f"category IN ({_category_values(FOOD_CATEGORIES_WITH_EGGS)})",
    )


def downgrade() -> None:
    op.drop_constraint("ck_shopping_list_items_category_allowed", "shopping_list_items", type_="check")
    op.drop_constraint("ck_food_items_category_allowed", "food_items", type_="check")

    op.execute("UPDATE shopping_list_items SET category = 'other' WHERE category = 'eggs'")
    op.execute("UPDATE food_items SET category = 'other' WHERE category = 'eggs'")

    op.create_check_constraint(
        "ck_food_items_category_allowed",
        "food_items",
        f"category IN ({_category_values(FOOD_CATEGORIES_WITHOUT_EGGS)})",
    )
    op.create_check_constraint(
        "ck_shopping_list_items_category_allowed",
        "shopping_list_items",
        f"category IN ({_category_values(FOOD_CATEGORIES_WITHOUT_EGGS)})",
    )
