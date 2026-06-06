"""make recipe owner nullable for system recipes

Revision ID: d8a6f3b1c2e4
Revises: c8f1e2d3a4b5
Create Date: 2026-06-05 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d8a6f3b1c2e4"
down_revision: Union[str, None] = "c8f1e2d3a4b5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("recipes_owner_user_id_fkey", "recipes", type_="foreignkey")
    op.alter_column("recipes", "owner_user_id", existing_type=sa.Integer(), nullable=True)
    op.create_foreign_key(
        "recipes_owner_user_id_fkey",
        "recipes",
        "users",
        ["owner_user_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("recipes_owner_user_id_fkey", "recipes", type_="foreignkey")
    op.alter_column("recipes", "owner_user_id", existing_type=sa.Integer(), nullable=False)
    op.create_foreign_key(
        "recipes_owner_user_id_fkey",
        "recipes",
        "users",
        ["owner_user_id"],
        ["id"],
        ondelete="CASCADE",
    )
