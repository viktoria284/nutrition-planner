"""add autoplan v3 preferences and recipe cook time

Revision ID: d4e7b1c3a9f0
Revises: c2e8f1a9b4d6
Create Date: 2026-05-13 14:10:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d4e7b1c3a9f0"
down_revision: Union[str, None] = "c2e8f1a9b4d6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("recipes", sa.Column("cook_time_minutes", sa.Integer(), nullable=True))
    op.create_check_constraint(
        "ck_recipes_cook_time_minutes_range",
        "recipes",
        "cook_time_minutes IS NULL OR (cook_time_minutes BETWEEN 1 AND 1440)",
    )

    op.add_column(
        "profiles",
        sa.Column("preferred_categories", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
    )
    op.add_column("profiles", sa.Column("max_cook_time_minutes", sa.Integer(), nullable=True))
    op.create_check_constraint(
        "ck_profiles_max_cook_time_minutes_range",
        "profiles",
        "max_cook_time_minutes IS NULL OR (max_cook_time_minutes BETWEEN 1 AND 1440)",
    )

    op.create_table(
        "profile_excluded_foods",
        sa.Column("profile_id", sa.Integer(), nullable=False),
        sa.Column("food_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["food_id"], ["food_items.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["profile_id"], ["profiles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("profile_id", "food_id"),
    )
    op.create_index(
        "ix_profile_excluded_foods_food_id",
        "profile_excluded_foods",
        ["food_id"],
        unique=False,
    )

    op.create_table(
        "profile_preferred_foods",
        sa.Column("profile_id", sa.Integer(), nullable=False),
        sa.Column("food_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["food_id"], ["food_items.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["profile_id"], ["profiles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("profile_id", "food_id"),
    )
    op.create_index(
        "ix_profile_preferred_foods_food_id",
        "profile_preferred_foods",
        ["food_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_profile_preferred_foods_food_id", table_name="profile_preferred_foods")
    op.drop_table("profile_preferred_foods")

    op.drop_index("ix_profile_excluded_foods_food_id", table_name="profile_excluded_foods")
    op.drop_table("profile_excluded_foods")

    op.drop_constraint("ck_profiles_max_cook_time_minutes_range", "profiles", type_="check")
    op.drop_column("profiles", "max_cook_time_minutes")
    op.drop_column("profiles", "preferred_categories")

    op.drop_constraint("ck_recipes_cook_time_minutes_range", "recipes", type_="check")
    op.drop_column("recipes", "cook_time_minutes")
