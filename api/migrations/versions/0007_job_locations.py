# ruff: noqa: E501
"""where the transporter was at pickup, at delivery and on the way (location tracking)

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-16
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "job_locations",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("transporter_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("lat", sa.Float(), nullable=False),
        sa.Column("lon", sa.Float(), nullable=False),
        sa.Column("accuracy_m", sa.Float(), nullable=True),
        sa.Column("distance_from_target_m", sa.Integer(), nullable=True),
        sa.Column("recorded_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("kind IN ('pickup', 'delivery', 'ping')", name=op.f("ck_job_locations_kind")),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], name=op.f("fk_job_locations_job_id_jobs")),
        sa.ForeignKeyConstraint(
            ["transporter_id"], ["transporters.id"], name=op.f("fk_job_locations_transporter_id_transporters")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_job_locations")),
    )
    op.create_index("ix_job_locations_job_id_recorded_at", "job_locations", ["job_id", "recorded_at"])


def downgrade() -> None:
    op.drop_index("ix_job_locations_job_id_recorded_at", table_name="job_locations")
    op.drop_table("job_locations")
