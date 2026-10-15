"""keep the village and district a lot was reported with (F1 web form slice)

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-16
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("lots", sa.Column("village_name", sa.Text(), nullable=True))
    op.add_column("lots", sa.Column("district", sa.Text(), nullable=True))
    op.add_column("lots", sa.Column("place_match", sa.Text(), nullable=True))
    # Lots made before this migration had a village row; copy its names across.
    op.execute(
        "UPDATE lots l SET village_name = v.name, district = v.district, place_match = 'exact' "
        "FROM villages v WHERE l.village_id = v.id"
    )


def downgrade() -> None:
    op.drop_column("lots", "place_match")
    op.drop_column("lots", "district")
    op.drop_column("lots", "village_name")
