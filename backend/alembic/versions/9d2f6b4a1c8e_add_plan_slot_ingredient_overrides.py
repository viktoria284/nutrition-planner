"""add plan slot ingredient overrides

Revision ID: 9d2f6b4a1c8e
Revises: 8c4f1a2b3d7e
Create Date: 2026-05-15 10:20:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "9d2f6b4a1c8e"
down_revision: Union[str, None] = "8c4f1a2b3d7e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "plan_slot_ingredient_overrides",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("slot_id", sa.Integer(), nullable=False),
        sa.Column("recipe_ingredient_id", sa.Integer(), nullable=True),
        sa.Column("food_id", sa.Integer(), nullable=True),
        sa.Column("grams", sa.Numeric(8, 2), nullable=True),
        sa.Column("is_excluded", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_manual", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["slot_id"], ["plan_slots.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["recipe_ingredient_id"], ["recipe_ingredients.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["food_id"], ["food_items.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slot_id", "recipe_ingredient_id", name="uq_slot_ingredient_overrides_slot_recipe_ingredient"),
        sa.CheckConstraint("grams IS NULL OR grams > 0", name="ck_slot_ingredient_overrides_grams_gt_0"),
        sa.CheckConstraint(
            "(is_manual = false AND recipe_ingredient_id IS NOT NULL) OR (is_manual = true AND recipe_ingredient_id IS NULL)",
            name="ck_slot_ingredient_overrides_manual_recipe_link",
        ),
        sa.CheckConstraint(
            "is_manual = false OR food_id IS NOT NULL",
            name="ck_slot_ingredient_overrides_manual_food_required",
        ),
        sa.CheckConstraint(
            "is_excluded = false OR grams IS NULL",
            name="ck_slot_ingredient_overrides_excluded_no_grams",
        ),
    )
    op.create_index(
        "ix_slot_ingredient_overrides_slot_id",
        "plan_slot_ingredient_overrides",
        ["slot_id"],
        unique=False,
    )
    op.create_index(
        "ix_slot_ingredient_overrides_recipe_ingredient_id",
        "plan_slot_ingredient_overrides",
        ["recipe_ingredient_id"],
        unique=False,
    )
    op.create_index(
        "ix_slot_ingredient_overrides_food_id",
        "plan_slot_ingredient_overrides",
        ["food_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_slot_ingredient_overrides_food_id", table_name="plan_slot_ingredient_overrides")
    op.drop_index("ix_slot_ingredient_overrides_recipe_ingredient_id", table_name="plan_slot_ingredient_overrides")
    op.drop_index("ix_slot_ingredient_overrides_slot_id", table_name="plan_slot_ingredient_overrides")
    op.drop_table("plan_slot_ingredient_overrides")
