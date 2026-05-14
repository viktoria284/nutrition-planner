"""add fiber nutrient and fiber targets

Revision ID: 8c4f1a2b3d7e
Revises: 7b1f2d9c4e6a
Create Date: 2026-05-14 20:30:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "8c4f1a2b3d7e"
down_revision: Union[str, None] = "7b1f2d9c4e6a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "food_items",
        sa.Column("fiber", sa.Numeric(6, 2), nullable=False, server_default=sa.text("0")),
    )
    op.create_check_constraint(
        "ck_food_items_fiber_non_negative",
        "food_items",
        "fiber >= 0",
    )
    op.create_check_constraint(
        "ck_food_items_fiber_max",
        "food_items",
        "fiber <= 100",
    )

    op.add_column("profiles", sa.Column("target_fiber", sa.Integer(), nullable=True))
    op.create_check_constraint(
        "ck_profiles_target_fiber_range",
        "profiles",
        "target_fiber IS NULL OR (target_fiber BETWEEN 0 AND 100)",
    )

    op.add_column("plans", sa.Column("target_fiber", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("plans", "target_fiber")

    op.drop_constraint("ck_profiles_target_fiber_range", "profiles", type_="check")
    op.drop_column("profiles", "target_fiber")

    op.drop_constraint("ck_food_items_fiber_max", "food_items", type_="check")
    op.drop_constraint("ck_food_items_fiber_non_negative", "food_items", type_="check")
    op.drop_column("food_items", "fiber")
