"""a farmer may sign up without a phone number (SMS verification is not required yet)

Revision ID: 0010
Revises: 0009
Create Date: 2026-10-16
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column("farmers", "phone", existing_type=sa.Text(), nullable=True)


def downgrade() -> None:
    op.alter_column("farmers", "phone", existing_type=sa.Text(), nullable=False)
