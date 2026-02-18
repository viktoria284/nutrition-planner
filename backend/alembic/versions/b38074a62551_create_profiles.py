"""create profiles

Revision ID: b38074a62551
Revises: 093e2e82f5bb
Create Date: 2026-02-18 23:36:46.741090

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b38074a62551'
down_revision: Union[str, None] = '093e2e82f5bb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "profiles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("target_kcal", sa.Integer(), nullable=False),
        sa.Column("target_protein", sa.Integer(), nullable=False),
        sa.Column("target_fat", sa.Integer(), nullable=False),
        sa.Column("target_carbs", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_profiles_user_id", "profiles", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_profiles_user_id", table_name="profiles")
    op.drop_table("profiles")
