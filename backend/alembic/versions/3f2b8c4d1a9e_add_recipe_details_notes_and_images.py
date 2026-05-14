"""add recipe instructions, image url and personal notes

Revision ID: 3f2b8c4d1a9e
Revises: d4e7b1c3a9f0
Create Date: 2026-05-14 12:10:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "3f2b8c4d1a9e"
down_revision: Union[str, None] = "d4e7b1c3a9f0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("recipes", sa.Column("instructions", sa.Text(), nullable=True))
    op.add_column("recipes", sa.Column("image_url", sa.String(length=2048), nullable=True))

    op.create_table(
        "recipe_notes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("recipe_id", sa.Integer(), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["recipe_id"], ["recipes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "recipe_id", name="uq_recipe_notes_user_recipe"),
        sa.CheckConstraint("length(trim(note)) > 0", name="ck_recipe_notes_note_not_blank"),
    )
    op.create_index("ix_recipe_notes_user_id", "recipe_notes", ["user_id"], unique=False)
    op.create_index("ix_recipe_notes_recipe_id", "recipe_notes", ["recipe_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_recipe_notes_recipe_id", table_name="recipe_notes")
    op.drop_index("ix_recipe_notes_user_id", table_name="recipe_notes")
    op.drop_table("recipe_notes")

    op.drop_column("recipes", "image_url")
    op.drop_column("recipes", "instructions")
