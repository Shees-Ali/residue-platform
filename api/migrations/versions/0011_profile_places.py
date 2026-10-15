"""factories and transporters remember the district and village they typed, and when they changed

Revision ID: 0011
Revises: 0010
Create Date: 2026-10-16
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES = ("factories", "transporters")


def upgrade() -> None:
    for t in TABLES:
        op.add_column(t, sa.Column("district", sa.Text(), nullable=True))
        op.add_column(t, sa.Column("village", sa.Text(), nullable=True))
        op.add_column(t, sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    for t in TABLES:
        op.drop_column(t, "updated_at")
        op.drop_column(t, "village")
        op.drop_column(t, "district")
