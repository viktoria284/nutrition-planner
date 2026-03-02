"""add recipe publication and reports

Revision ID: 7aa2d6b9c3ef
Revises: 1c2e6f9a8b44
Create Date: 2026-03-02 11:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "7aa2d6b9c3ef"
down_revision: Union[str, None] = "1c2e6f9a8b44"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "recipes",
        sa.Column(
            "source",
            postgresql.ENUM("private", "verified", "community", name="food_source", create_type=False),
            nullable=False,
            server_default="private",
        ),
    )
    op.add_column(
        "recipes",
        sa.Column(
            "status",
            postgresql.ENUM("draft", "pending", "approved", "rejected", name="food_status", create_type=False),
            nullable=False,
            server_default="draft",
        ),
    )
    op.add_column("recipes", sa.Column("is_listed", sa.Boolean(), nullable=False, server_default=sa.text("true")))
    op.add_column("recipes", sa.Column("reports_count", sa.Integer(), nullable=False, server_default="0"))

    op.create_index("ix_recipes_source_status_is_listed", "recipes", ["source", "status", "is_listed"], unique=False)

    op.create_table(
        "recipe_reports",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("recipe_id", sa.Integer(), nullable=False),
        sa.Column("reporter_user_id", sa.Integer(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["recipe_id"], ["recipes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reporter_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("recipe_id", "reporter_user_id", name="uq_recipe_reports_recipe_reporter"),
    )
    op.create_index("ix_recipe_reports_recipe_id", "recipe_reports", ["recipe_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_recipe_reports_recipe_id", table_name="recipe_reports")
    op.drop_table("recipe_reports")

    op.drop_index("ix_recipes_source_status_is_listed", table_name="recipes")
    op.drop_column("recipes", "reports_count")
    op.drop_column("recipes", "is_listed")
    op.drop_column("recipes", "status")
    op.drop_column("recipes", "source")
