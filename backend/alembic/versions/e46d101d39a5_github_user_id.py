"""github user id

Revision ID: e46d101d39a5
Revises: dfa612ec1b2e
Create Date: 2026-09-08 22:49:09.854488
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e46d101d39a5'
down_revision: Union[str, None] = 'dfa612ec1b2e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("github_user_id", sa.String(), nullable=True))
    op.create_index("ix_users_github_user_id", "users", ["github_user_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_users_github_user_id", table_name="users")
    op.drop_column("users", "github_user_id")
