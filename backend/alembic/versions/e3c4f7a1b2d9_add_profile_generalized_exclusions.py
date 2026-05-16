"""add profile generalized exclusions

Revision ID: e3c4f7a1b2d9
Revises: c9d1a4e8b2f7
Create Date: 2026-05-16 13:40:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "e3c4f7a1b2d9"
down_revision = "c9d1a4e8b2f7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "profiles",
        sa.Column("excluded_categories", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
    )
    op.add_column(
        "profiles",
        sa.Column("excluded_terms", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
    )


def downgrade() -> None:
    op.drop_column("profiles", "excluded_terms")
    op.drop_column("profiles", "excluded_categories")
