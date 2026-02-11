"""add user_role enum and users.role

Revision ID: 983d32ec5302
Revises: cd236685c140
Create Date: 2026-02-11 18:42:41.237542

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '983d32ec5302'
down_revision: Union[str, None] = 'cd236685c140'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


user_role_enum = sa.Enum("user", "admin", name="user_role")

def upgrade() -> None:
    bind = op.get_bind()
    user_role_enum.create(bind, checkfirst=True)

    op.add_column(
        "users",
        sa.Column("role", user_role_enum, nullable=False, server_default="user"),
    )

def downgrade() -> None:
    bind = op.get_bind()
    op.drop_column("users", "role")
    user_role_enum.drop(bind, checkfirst=True)