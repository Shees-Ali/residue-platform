# ruff: noqa: E501
"""the event log and per-person notifications (EV1 to EV7)

Revision ID: 0012
Revises: 0011
Create Date: 2026-10-16
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "events",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("lot_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("order_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("actor_uid", sa.Text(), nullable=True),
        sa.Column("actor_role", sa.Text(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("data", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("visible_to", postgresql.ARRAY(sa.Text()), server_default=sa.text("'{}'"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], name=op.f("fk_events_job_id_jobs")),
        sa.ForeignKeyConstraint(["lot_id"], ["lots.id"], name=op.f("fk_events_lot_id_lots")),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], name=op.f("fk_events_order_id_orders")),
        sa.ForeignKeyConstraint(["actor_uid"], ["users.uid"], name=op.f("fk_events_actor_uid_users")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_events")),
    )
    op.create_index("ix_events_job_id_created_at", "events", ["job_id", "created_at"])
    op.create_table(
        "notifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("recipient_uid", sa.Text(), nullable=True),
        sa.Column("recipient_farmer_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column("level", sa.Text(), server_default=sa.text("'info'"), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("refresh", postgresql.ARRAY(sa.Text()), server_default=sa.text("'{}'"), nullable=False),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"], name=op.f("fk_notifications_event_id_events")),
        sa.ForeignKeyConstraint(["recipient_uid"], ["users.uid"], name=op.f("fk_notifications_recipient_uid_users")),
        sa.ForeignKeyConstraint(["recipient_farmer_id"], ["farmers.id"], name=op.f("fk_notifications_recipient_farmer_id_farmers")),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], name=op.f("fk_notifications_job_id_jobs")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_notifications")),
    )
    op.create_index(
        "uq_notifications_event_recipient_uid", "notifications", ["event_id", "recipient_uid"],
        unique=True, postgresql_where=sa.text("recipient_uid IS NOT NULL"),
    )
    op.create_index(
        "uq_notifications_event_recipient_farmer", "notifications", ["event_id", "recipient_farmer_id"],
        unique=True, postgresql_where=sa.text("recipient_farmer_id IS NOT NULL"),
    )
    op.create_index("ix_notifications_recipient_uid_created_at", "notifications", ["recipient_uid", "created_at"])
    op.create_index(
        "ix_notifications_undelivered", "notifications", ["created_at"],
        postgresql_where=sa.text("delivered_at IS NULL AND recipient_uid IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_table("notifications")
    op.drop_table("events")
