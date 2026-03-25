"""add plans foundation

Revision ID: c1d4f5a6b7e8
Revises: 7aa2d6b9c3ef
Create Date: 2026-03-24 12:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c1d4f5a6b7e8"
down_revision: Union[str, None] = "7aa2d6b9c3ef"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "plans",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("days_count", sa.Integer(), nullable=False),
        sa.Column("meals_per_day", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=120), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("days_count BETWEEN 1 AND 7", name="ck_plans_days_count_between_1_7"),
        sa.CheckConstraint("meals_per_day BETWEEN 2 AND 6", name="ck_plans_meals_per_day_between_2_6"),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_plans_owner_user_id", "plans", ["owner_user_id"], unique=False)

    op.create_table(
        "plan_slots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("plan_id", sa.Integer(), nullable=False),
        sa.Column("day_date", sa.Date(), nullable=False),
        sa.Column("slot_index", sa.Integer(), nullable=False),
        sa.Column("recipe_id", sa.Integer(), nullable=True),
        sa.Column("servings_multiplier", sa.Numeric(precision=8, scale=3), nullable=False, server_default=sa.text("1")),
        sa.Column("pinned", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("slot_index >= 0", name="ck_plan_slots_slot_index_ge_0"),
        sa.CheckConstraint("servings_multiplier > 0", name="ck_plan_slots_servings_multiplier_gt_0"),
        sa.ForeignKeyConstraint(["plan_id"], ["plans.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["recipe_id"], ["recipes.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("plan_id", "day_date", "slot_index", name="uq_plan_slots_plan_day_slot"),
    )
    op.create_index("ix_plan_slots_recipe_id", "plan_slots", ["recipe_id"], unique=False)
    op.create_index("ix_plan_slots_plan_id_day_date", "plan_slots", ["plan_id", "day_date"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_plan_slots_plan_id_day_date", table_name="plan_slots")
    op.drop_index("ix_plan_slots_recipe_id", table_name="plan_slots")
    op.drop_table("plan_slots")

    op.drop_index("ix_plans_owner_user_id", table_name="plans")
    op.drop_table("plans")
