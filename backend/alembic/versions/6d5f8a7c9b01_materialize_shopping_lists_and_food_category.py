"""materialize shopping lists and add food category

Revision ID: 6d5f8a7c9b01
Revises: a4b7c8d9e0f1
Create Date: 2026-05-10 13:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "6d5f8a7c9b01"
down_revision: Union[str, None] = "a4b7c8d9e0f1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

FOOD_CATEGORIES = (
    "vegetables",
    "fruits",
    "dairy",
    "meat_fish",
    "grains_bakery",
    "pantry_spices",
    "nuts_oils",
    "drinks",
    "sweets",
    "frozen",
    "other",
)


FOOD_CATEGORY_SQL_VALUES = ", ".join(f"'{value}'" for value in FOOD_CATEGORIES)


def upgrade() -> None:
    op.add_column(
        "food_items",
        sa.Column("category", sa.String(length=32), nullable=False, server_default="other"),
    )
    op.create_check_constraint(
        "ck_food_items_category_allowed",
        "food_items",
        f"category IN ({FOOD_CATEGORY_SQL_VALUES})",
    )

    op.drop_table("shopping_overrides")
    op.drop_table("shopping_manual_items")

    op.create_table(
        "shopping_lists",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("source_type", sa.String(length=32), nullable=False, server_default="plan"),
        sa.Column("source_signature", sa.String(length=128), nullable=True),
        sa.Column("is_outdated", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("length(trim(title)) > 0", name="ck_shopping_lists_title_not_blank"),
        sa.CheckConstraint("status IN ('active', 'archived')", name="ck_shopping_lists_status_allowed"),
        sa.CheckConstraint("source_type IN ('plan')", name="ck_shopping_lists_source_type_allowed"),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_shopping_lists_owner_user_id", "shopping_lists", ["owner_user_id"], unique=False)

    op.create_table(
        "shopping_list_sources",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("shopping_list_id", sa.Integer(), nullable=False),
        sa.Column("plan_id", sa.Integer(), nullable=False),
        sa.Column("date_from", sa.Date(), nullable=True),
        sa.Column("date_to", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["plan_id"], ["plans.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["shopping_list_id"], ["shopping_lists.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_shopping_list_sources_shopping_list_id", "shopping_list_sources", ["shopping_list_id"], unique=False)
    op.create_index("ix_shopping_list_sources_plan_id", "shopping_list_sources", ["plan_id"], unique=False)

    op.create_table(
        "shopping_list_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("shopping_list_id", sa.Integer(), nullable=False),
        sa.Column("food_id", sa.Integer(), nullable=True),
        sa.Column("name_snapshot", sa.String(length=255), nullable=False),
        sa.Column("category", sa.String(length=32), nullable=False, server_default="other"),
        sa.Column("item_type", sa.String(length=16), nullable=False),
        sa.Column("planned_grams", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("adjusted_grams", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("unit", sa.String(length=32), nullable=False, server_default="g"),
        sa.Column("checked", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("excluded", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("length(trim(name_snapshot)) > 0", name="ck_shopping_list_items_name_not_blank"),
        sa.CheckConstraint(f"category IN ({FOOD_CATEGORY_SQL_VALUES})", name="ck_shopping_list_items_category_allowed"),
        sa.CheckConstraint("item_type IN ('computed', 'manual')", name="ck_shopping_list_items_item_type_allowed"),
        sa.CheckConstraint("planned_grams IS NULL OR planned_grams > 0", name="ck_shopping_list_items_planned_grams_gt_0"),
        sa.CheckConstraint(
            "adjusted_grams IS NULL OR adjusted_grams > 0",
            name="ck_shopping_list_items_adjusted_grams_gt_0",
        ),
        sa.CheckConstraint("length(trim(unit)) > 0", name="ck_shopping_list_items_unit_not_blank"),
        sa.ForeignKeyConstraint(["food_id"], ["food_items.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["shopping_list_id"], ["shopping_lists.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_shopping_list_items_shopping_list_id", "shopping_list_items", ["shopping_list_id"], unique=False)
    op.create_index("ix_shopping_list_items_food_id", "shopping_list_items", ["food_id"], unique=False)
    op.create_index(
        "ix_shopping_list_items_list_sort",
        "shopping_list_items",
        ["shopping_list_id", "sort_order", "id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_shopping_list_items_list_sort", table_name="shopping_list_items")
    op.drop_index("ix_shopping_list_items_food_id", table_name="shopping_list_items")
    op.drop_index("ix_shopping_list_items_shopping_list_id", table_name="shopping_list_items")
    op.drop_table("shopping_list_items")

    op.drop_index("ix_shopping_list_sources_plan_id", table_name="shopping_list_sources")
    op.drop_index("ix_shopping_list_sources_shopping_list_id", table_name="shopping_list_sources")
    op.drop_table("shopping_list_sources")

    op.drop_index("ix_shopping_lists_owner_user_id", table_name="shopping_lists")
    op.drop_table("shopping_lists")

    op.create_table(
        "shopping_overrides",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("plan_id", sa.Integer(), nullable=False),
        sa.Column("food_id", sa.Integer(), nullable=False),
        sa.Column("checked", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("adjusted_grams", sa.Numeric(precision=9, scale=2), nullable=True),
        sa.Column("excluded", sa.Boolean(), nullable=False, server_default=sa.text("false")),
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

    op.drop_constraint("ck_food_items_category_allowed", "food_items", type_="check")
    op.drop_column("food_items", "category")
