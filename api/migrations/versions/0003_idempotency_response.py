"""idempotency keys keep the original response so replays return it

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-14
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # response IS NULL means the first request is still in flight
    op.add_column("idempotency_keys", sa.Column("request_hash", sa.Text(), nullable=True))
    op.add_column("idempotency_keys", sa.Column("status_code", sa.Integer(), nullable=True))
    op.add_column(
        "idempotency_keys",
        sa.Column("response", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("idempotency_keys", "response")
    op.drop_column("idempotency_keys", "status_code")
    op.drop_column("idempotency_keys", "request_hash")
