"""add user pantry items and shopping item flag

Revision ID: a6f9b2c3d4e5
Revises: e3c4f7a1b2d9
Create Date: 2026-05-16 19:30:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "a6f9b2c3d4e5"
down_revision = "e3c4f7a1b2d9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_pantry_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("food_id", sa.Integer(), nullable=False),
        sa.Column("note", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["food_id"], ["food_items.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "food_id", name="uq_user_pantry_items_user_food"),
    )
    op.create_index(op.f("ix_user_pantry_items_food_id"), "user_pantry_items", ["food_id"], unique=False)
    op.create_index(op.f("ix_user_pantry_items_user_id"), "user_pantry_items", ["user_id"], unique=False)

    op.add_column(
        "shopping_list_items",
        sa.Column(
            "in_pantry_section",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )


def downgrade() -> None:
    op.drop_column("shopping_list_items", "in_pantry_section")
    op.drop_index(op.f("ix_user_pantry_items_user_id"), table_name="user_pantry_items")
    op.drop_index(op.f("ix_user_pantry_items_food_id"), table_name="user_pantry_items")
    op.drop_table("user_pantry_items")
