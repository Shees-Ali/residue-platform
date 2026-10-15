# ruff: noqa: E501
"""an escalation can come from a job (a farmer disputing on the web), not only from a call

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-16
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column("escalations", "call_id", existing_type=postgresql.UUID(as_uuid=True), nullable=True)
    op.add_column("escalations", sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(op.f("fk_escalations_job_id_jobs"), "escalations", "jobs", ["job_id"], ["id"])


def downgrade() -> None:
    op.drop_constraint(op.f("fk_escalations_job_id_jobs"), "escalations", type_="foreignkey")
    op.drop_column("escalations", "job_id")
    op.execute("DELETE FROM escalations WHERE call_id IS NULL")
    op.alter_column("escalations", "call_id", existing_type=postgresql.UUID(as_uuid=True), nullable=False)
