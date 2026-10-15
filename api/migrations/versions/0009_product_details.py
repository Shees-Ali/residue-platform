# ruff: noqa: E501
"""products carry a category, a unit and a description (the marketplace shows them)

Revision ID: 0009
Revises: 0008
Create Date: 2026-10-16
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CATEGORIES = ("Clean Energy", "Farming & Garden", "Building Materials", "Home & Living")


def upgrade() -> None:
    op.add_column("products", sa.Column("category", sa.Text(), server_default=sa.text("'Clean Energy'"), nullable=False))
    op.add_column("products", sa.Column("unit", sa.Text(), server_default=sa.text("'per 25 kg bag'"), nullable=False))
    op.add_column("products", sa.Column("description", sa.Text(), server_default=sa.text("''"), nullable=False))
    # products listed before this migration: place the obvious ones, leave the rest as clean energy
    op.execute("UPDATE products SET category = 'Farming & Garden' WHERE name ILIKE '%compost%'")
    op.create_check_constraint(
        op.f("ck_products_category"),
        "products",
        "category IN (" + ", ".join(f"'{c}'" for c in CATEGORIES) + ")",
    )


def downgrade() -> None:
    op.drop_constraint(op.f("ck_products_category"), "products", type_="check")
    op.drop_column("products", "description")
    op.drop_column("products", "unit")
    op.drop_column("products", "category")
