"""add author favorites

Revision ID: c9d1a4e8b2f7
Revises: b5d4e8f1a2c3
Create Date: 2026-05-16 12:30:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "c9d1a4e8b2f7"
down_revision = "b5d4e8f1a2c3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "author_favorites",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("author_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["author_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "author_id", name="uq_author_favorites_user_author"),
    )
    op.create_index("ix_author_favorites_user_id", "author_favorites", ["user_id"], unique=False)
    op.create_index("ix_author_favorites_author_id", "author_favorites", ["author_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_author_favorites_author_id", table_name="author_favorites")
    op.drop_index("ix_author_favorites_user_id", table_name="author_favorites")
    op.drop_table("author_favorites")
