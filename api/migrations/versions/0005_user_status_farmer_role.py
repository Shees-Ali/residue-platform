"""farmer role, user status and email, farmer-to-user link (auth and roles)

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-15
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OLD_ROLES = ("admin", "transporter", "factory", "buyer")
NEW_ROLES = OLD_ROLES + ("farmer",)
STATUSES = ("active", "pending", "suspended")


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN (" + ", ".join(f"'{v}'" for v in values) + ")"


def upgrade() -> None:
    op.drop_constraint(op.f("ck_users_role"), "users", type_="check")
    op.create_check_constraint(op.f("ck_users_role"), "users", _in("role", NEW_ROLES))
    # Existing (seeded) users stay usable: the default is active.
    op.add_column(
        "users", sa.Column("status", sa.Text(), server_default=sa.text("'active'"), nullable=False)
    )
    op.create_check_constraint(op.f("ck_users_status"), "users", _in("status", STATUSES))
    op.add_column("users", sa.Column("email", sa.Text(), nullable=True))
    op.create_unique_constraint(op.f("uq_users_email"), "users", ["email"])
    op.add_column("farmers", sa.Column("user_uid", sa.Text(), nullable=True))
    op.create_foreign_key(
        op.f("fk_farmers_user_uid_users"), "farmers", "users", ["user_uid"], ["uid"]
    )
    op.create_unique_constraint(op.f("uq_farmers_user_uid"), "farmers", ["user_uid"])


def downgrade() -> None:
    op.drop_constraint(op.f("uq_farmers_user_uid"), "farmers", type_="unique")
    op.drop_constraint(op.f("fk_farmers_user_uid_users"), "farmers", type_="foreignkey")
    op.drop_column("farmers", "user_uid")
    op.drop_constraint(op.f("uq_users_email"), "users", type_="unique")
    op.drop_column("users", "email")
    op.drop_constraint(op.f("ck_users_status"), "users", type_="check")
    op.drop_column("users", "status")
    op.execute("DELETE FROM users WHERE role = 'farmer'")
    op.drop_constraint(op.f("ck_users_role"), "users", type_="check")
    op.create_check_constraint(op.f("ck_users_role"), "users", _in("role", OLD_ROLES))
