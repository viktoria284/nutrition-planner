"""add plan shopping state

Revision ID: e5f7a9c2d1b4
Revises: c1d4f5a6b7e8
Create Date: 2026-03-26 14:20:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "e5f7a9c2d1b4"
down_revision: Union[str, None] = "c1d4f5a6b7e8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "shopping_overrides",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("plan_id", sa.Integer(), nullable=False),
        sa.Column("food_id", sa.Integer(), nullable=False),
        sa.Column("checked", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("adjusted_grams", sa.Numeric(precision=9, scale=2), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint(
            "adjusted_grams IS NULL OR adjusted_grams > 0",
            name="ck_shopping_overrides_adjusted_grams_gt_0",
        ),
        sa.ForeignKeyConstraint(["food_id"], ["food_items.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["plan_id"], ["plans.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("plan_id", "food_id", name="uq_shopping_overrides_plan_food"),
    )
    op.create_index("ix_shopping_overrides_plan_id", "shopping_overrides", ["plan_id"], unique=False)
    op.create_index("ix_shopping_overrides_food_id", "shopping_overrides", ["food_id"], unique=False)

    op.create_table(
        "shopping_manual_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("plan_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("grams", sa.Numeric(precision=9, scale=2), nullable=True),
        sa.Column("unit", sa.String(length=32), nullable=True),
        sa.Column("checked", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("length(trim(name)) > 0", name="ck_shopping_manual_items_name_not_blank"),
        sa.CheckConstraint("grams IS NULL OR grams > 0", name="ck_shopping_manual_items_grams_gt_0"),
        sa.ForeignKeyConstraint(["plan_id"], ["plans.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_shopping_manual_items_plan_id", "shopping_manual_items", ["plan_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_shopping_manual_items_plan_id", table_name="shopping_manual_items")
    op.drop_table("shopping_manual_items")

    op.drop_index("ix_shopping_overrides_food_id", table_name="shopping_overrides")
    op.drop_index("ix_shopping_overrides_plan_id", table_name="shopping_overrides")
    op.drop_table("shopping_overrides")
