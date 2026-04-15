"""add profile snapshot targets to plans

Revision ID: a4b7c8d9e0f1
Revises: f2a6c9d4e1b0
Create Date: 2026-04-13 11:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a4b7c8d9e0f1"
down_revision: Union[str, None] = "f2a6c9d4e1b0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("plans", sa.Column("profile_id", sa.Integer(), nullable=True))
    op.add_column("plans", sa.Column("target_kcal", sa.Integer(), nullable=True))
    op.add_column("plans", sa.Column("target_protein", sa.Integer(), nullable=True))
    op.add_column("plans", sa.Column("target_fat", sa.Integer(), nullable=True))
    op.add_column("plans", sa.Column("target_carbs", sa.Integer(), nullable=True))

    op.create_index("ix_plans_profile_id", "plans", ["profile_id"], unique=False)
    op.create_foreign_key(
        "fk_plans_profile_id_profiles",
        "plans",
        "profiles",
        ["profile_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_plans_profile_id_profiles", "plans", type_="foreignkey")
    op.drop_index("ix_plans_profile_id", table_name="plans")

    op.drop_column("plans", "target_carbs")
    op.drop_column("plans", "target_fat")
    op.drop_column("plans", "target_protein")
    op.drop_column("plans", "target_kcal")
    op.drop_column("plans", "profile_id")
