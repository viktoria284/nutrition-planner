"""add admin report resolution fields

Revision ID: ab3e1d7f9c2a
Revises: 9d2f6b4a1c8e
Create Date: 2026-05-15 09:40:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "ab3e1d7f9c2a"
down_revision = "9d2f6b4a1c8e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("food_reports", sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("food_reports", sa.Column("resolved_by_admin_id", sa.Integer(), nullable=True))
    op.add_column("food_reports", sa.Column("resolution", sa.String(length=32), nullable=True))
    op.add_column("food_reports", sa.Column("admin_comment", sa.Text(), nullable=True))
    op.create_foreign_key(
        "fk_food_reports_resolved_by_admin_id_users",
        "food_reports",
        "users",
        ["resolved_by_admin_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.add_column("recipe_reports", sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("recipe_reports", sa.Column("resolved_by_admin_id", sa.Integer(), nullable=True))
    op.add_column("recipe_reports", sa.Column("resolution", sa.String(length=32), nullable=True))
    op.add_column("recipe_reports", sa.Column("admin_comment", sa.Text(), nullable=True))
    op.create_foreign_key(
        "fk_recipe_reports_resolved_by_admin_id_users",
        "recipe_reports",
        "users",
        ["resolved_by_admin_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_recipe_reports_resolved_by_admin_id_users", "recipe_reports", type_="foreignkey")
    op.drop_column("recipe_reports", "admin_comment")
    op.drop_column("recipe_reports", "resolution")
    op.drop_column("recipe_reports", "resolved_by_admin_id")
    op.drop_column("recipe_reports", "resolved_at")

    op.drop_constraint("fk_food_reports_resolved_by_admin_id_users", "food_reports", type_="foreignkey")
    op.drop_column("food_reports", "admin_comment")
    op.drop_column("food_reports", "resolution")
    op.drop_column("food_reports", "resolved_by_admin_id")
    op.drop_column("food_reports", "resolved_at")
