"""add is_listed to food_items

Revision ID: f7c3d912ab4e
Revises: 9b9d53a4b6ec
Create Date: 2026-03-01 00:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f7c3d912ab4e"
down_revision: Union[str, None] = "9b9d53a4b6ec"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "food_items",
        sa.Column("is_listed", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_index(
        "ix_food_items_source_status_is_listed",
        "food_items",
        ["source", "status", "is_listed"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_food_items_source_status_is_listed", table_name="food_items")
    op.drop_column("food_items", "is_listed")
