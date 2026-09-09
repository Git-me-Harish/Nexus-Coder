"""user profile fields

Revision ID: dfa612ec1b2e
Revises: 5c630784a07e
Create Date: 2026-09-08 22:17:20.679957
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'dfa612ec1b2e'
down_revision: Union[str, None] = '5c630784a07e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("bio", sa.String(), nullable=True))
    op.add_column("users", sa.Column("company", sa.String(), nullable=True))
    op.add_column("users", sa.Column("location", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "location")
    op.drop_column("users", "company")
    op.drop_column("users", "bio")
