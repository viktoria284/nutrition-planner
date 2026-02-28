"""add food reports and reports_count

Revision ID: 9b9d53a4b6ec
Revises: 64f3a8c91b2e
Create Date: 2026-02-28 15:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "9b9d53a4b6ec"
down_revision: Union[str, None] = "64f3a8c91b2e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "food_items",
        sa.Column("reports_count", sa.Integer(), nullable=False, server_default="0"),
    )

    op.create_table(
        "food_reports",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("food_id", sa.Integer(), nullable=False),
        sa.Column("reporter_user_id", sa.Integer(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["food_id"], ["food_items.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reporter_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("food_id", "reporter_user_id", name="uq_food_reports_food_reporter"),
    )
    op.create_index("ix_food_reports_food_id", "food_reports", ["food_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_food_reports_food_id", table_name="food_reports")
    op.drop_table("food_reports")
    op.drop_column("food_items", "reports_count")
