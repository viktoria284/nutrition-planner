"""add foods foundation

Revision ID: 64f3a8c91b2e
Revises: ec6e2982f4dd
Create Date: 2026-02-23 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "64f3a8c91b2e"
down_revision: Union[str, None] = "ec6e2982f4dd"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

food_source_enum = postgresql.ENUM("private", "verified", "community", name="food_source")
food_status_enum = postgresql.ENUM("draft", "pending", "approved", "rejected", name="food_status")


def upgrade() -> None:
    bind = op.get_bind()
    food_source_enum.create(bind, checkfirst=True)
    food_status_enum.create(bind, checkfirst=True)

    op.create_table(
        "food_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("brand", sa.String(length=255), nullable=True),
        sa.Column("kcal", sa.Numeric(precision=8, scale=2), nullable=False),
        sa.Column("protein", sa.Numeric(precision=6, scale=2), nullable=False),
        sa.Column("fat", sa.Numeric(precision=6, scale=2), nullable=False),
        sa.Column("carbs", sa.Numeric(precision=6, scale=2), nullable=False),
        sa.Column(
            "source",
            postgresql.ENUM("private", "verified", "community", name="food_source", create_type=False),
            nullable=False,
            server_default="private",
        ),
        sa.Column(
            "status",
            postgresql.ENUM("draft", "pending", "approved", "rejected", name="food_status", create_type=False),
            nullable=False,
            server_default="draft",
        ),
        sa.Column("owner_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("length(trim(name)) > 0", name="ck_food_items_name_not_blank"),
        sa.CheckConstraint("(source != 'verified') OR owner_user_id IS NULL", name="ck_food_items_verified_owner_null"),
        sa.CheckConstraint("kcal >= 0", name="ck_food_items_kcal_non_negative"),
        sa.CheckConstraint("protein >= 0", name="ck_food_items_protein_non_negative"),
        sa.CheckConstraint("fat >= 0", name="ck_food_items_fat_non_negative"),
        sa.CheckConstraint("carbs >= 0", name="ck_food_items_carbs_non_negative"),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_food_items_owner_user_id", "food_items", ["owner_user_id"], unique=False)
    op.create_index("ix_food_items_name_lower", "food_items", [sa.text("lower(name)")], unique=False)

    op.create_table(
        "food_servings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("food_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("grams", sa.Numeric(precision=7, scale=2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("length(trim(name)) > 0", name="ck_food_servings_name_not_blank"),
        sa.CheckConstraint("grams > 0", name="ck_food_servings_grams_positive"),
        sa.ForeignKeyConstraint(["food_id"], ["food_items.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_food_servings_food_id", "food_servings", ["food_id"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()

    op.drop_index("ix_food_servings_food_id", table_name="food_servings")
    op.drop_table("food_servings")

    op.drop_index("ix_food_items_name_lower", table_name="food_items")
    op.drop_index("ix_food_items_owner_user_id", table_name="food_items")
    op.drop_table("food_items")

    food_status_enum.drop(bind, checkfirst=True)
    food_source_enum.drop(bind, checkfirst=True)
