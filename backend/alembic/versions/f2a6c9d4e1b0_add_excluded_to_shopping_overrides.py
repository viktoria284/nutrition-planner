"""add excluded flag to shopping overrides

Revision ID: f2a6c9d4e1b0
Revises: e5f7a9c2d1b4
Create Date: 2026-03-26 16:05:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f2a6c9d4e1b0"
down_revision: Union[str, None] = "e5f7a9c2d1b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "shopping_overrides",
        sa.Column("excluded", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )


def downgrade() -> None:
    op.drop_column("shopping_overrides", "excluded")
