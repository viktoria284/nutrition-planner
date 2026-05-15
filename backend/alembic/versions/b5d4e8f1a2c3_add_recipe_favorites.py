"""add recipe favorites

Revision ID: b5d4e8f1a2c3
Revises: ab3e1d7f9c2a
Create Date: 2026-05-15 15:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "b5d4e8f1a2c3"
down_revision = "ab3e1d7f9c2a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "recipe_favorites",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("recipe_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["recipe_id"], ["recipes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "recipe_id", name="uq_recipe_favorites_user_recipe"),
    )
    op.create_index("ix_recipe_favorites_user_id", "recipe_favorites", ["user_id"], unique=False)
    op.create_index("ix_recipe_favorites_recipe_id", "recipe_favorites", ["recipe_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_recipe_favorites_recipe_id", table_name="recipe_favorites")
    op.drop_index("ix_recipe_favorites_user_id", table_name="recipe_favorites")
    op.drop_table("recipe_favorites")
