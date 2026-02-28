"""add max nutrient constraints to food_items

Revision ID: 2c1f4aa8d9b7
Revises: f7c3d912ab4e
Create Date: 2026-03-01 02:05:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "2c1f4aa8d9b7"
down_revision: Union[str, None] = "f7c3d912ab4e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_check_constraint(
        "ck_food_items_kcal_max",
        "food_items",
        "kcal <= 1000",
    )
    op.create_check_constraint(
        "ck_food_items_protein_max",
        "food_items",
        "protein <= 100",
    )
    op.create_check_constraint(
        "ck_food_items_fat_max",
        "food_items",
        "fat <= 100",
    )
    op.create_check_constraint(
        "ck_food_items_carbs_max",
        "food_items",
        "carbs <= 100",
    )


def downgrade() -> None:
    op.drop_constraint("ck_food_items_carbs_max", "food_items", type_="check")
    op.drop_constraint("ck_food_items_fat_max", "food_items", type_="check")
    op.drop_constraint("ck_food_items_protein_max", "food_items", type_="check")
    op.drop_constraint("ck_food_items_kcal_max", "food_items", type_="check")
