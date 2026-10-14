"""ledger kinds for the factory and NGO shares of a product sale (FA3/B1)

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-14
"""
from collections.abc import Sequence

from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OLD = ("escrow_in", "release_farmer", "release_transporter", "platform_fee", "refund")
NEW = OLD + ("release_factory", "release_ngo")


def _kinds(values: tuple[str, ...]) -> str:
    return "kind IN (" + ", ".join(f"'{v}'" for v in values) + ")"


def upgrade() -> None:
    op.drop_constraint(op.f("ck_ledger_entries_kind"), "ledger_entries", type_="check")
    op.create_check_constraint(op.f("ck_ledger_entries_kind"), "ledger_entries", _kinds(NEW))


def downgrade() -> None:
    op.drop_constraint(op.f("ck_ledger_entries_kind"), "ledger_entries", type_="check")
    op.create_check_constraint(op.f("ck_ledger_entries_kind"), "ledger_entries", _kinds(OLD))
