"""make profile targets nullable

Revision ID: ec6e2982f4dd
Revises: b38074a62551
Create Date: 2026-02-19 00:26:39.973069

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ec6e2982f4dd'
down_revision: Union[str, None] = 'b38074a62551'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("profiles", "target_kcal", existing_type=sa.Integer(), nullable=True)
    op.alter_column("profiles", "target_protein", existing_type=sa.Integer(), nullable=True)
    op.alter_column("profiles", "target_fat", existing_type=sa.Integer(), nullable=True)
    op.alter_column("profiles", "target_carbs", existing_type=sa.Integer(), nullable=True)


def downgrade() -> None:
    op.execute(sa.text("UPDATE profiles SET target_kcal = 0 WHERE target_kcal IS NULL"))
    op.execute(sa.text("UPDATE profiles SET target_protein = 0 WHERE target_protein IS NULL"))
    op.execute(sa.text("UPDATE profiles SET target_fat = 0 WHERE target_fat IS NULL"))
    op.execute(sa.text("UPDATE profiles SET target_carbs = 0 WHERE target_carbs IS NULL"))

    op.alter_column("profiles", "target_kcal", existing_type=sa.Integer(), nullable=False)
    op.alter_column("profiles", "target_protein", existing_type=sa.Integer(), nullable=False)
    op.alter_column("profiles", "target_fat", existing_type=sa.Integer(), nullable=False)
    op.alter_column("profiles", "target_carbs", existing_type=sa.Integer(), nullable=False)
