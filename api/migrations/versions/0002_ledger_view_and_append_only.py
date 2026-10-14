"""ledger_balance view and append-only ledger trigger

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-14
"""
from collections.abc import Sequence

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # A3: per job, money in vs money out. `balanced` is true when escrow_in equals releases + fees
    # + refunds (mid-job it is false by design: funded but not yet released).
    op.execute(
        """
        CREATE VIEW ledger_balance AS
        SELECT
            job_id,
            COALESCE(SUM(amount) FILTER (WHERE kind = 'escrow_in'), 0) AS escrow_in,
            COALESCE(SUM(amount) FILTER (WHERE kind <> 'escrow_in'), 0) AS paid_out,
            COALESCE(SUM(amount) FILTER (WHERE kind = 'escrow_in'), 0)
              = COALESCE(SUM(amount) FILTER (WHERE kind <> 'escrow_in'), 0) AS balanced
        FROM ledger_entries
        WHERE job_id IS NOT NULL
        GROUP BY job_id
        """
    )
    op.execute(
        """
        CREATE FUNCTION ledger_entries_append_only() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'ledger_entries is append-only';
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER ledger_entries_no_change
        BEFORE UPDATE OR DELETE ON ledger_entries
        FOR EACH ROW EXECUTE FUNCTION ledger_entries_append_only()
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER ledger_entries_no_change ON ledger_entries")
    op.execute("DROP FUNCTION ledger_entries_append_only()")
    op.execute("DROP VIEW ledger_balance")
