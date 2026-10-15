import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, MetaData, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

NAMING = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING)


def uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )


def created_at() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), server_default=func.now())


def updated_at() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


def one_of(column: str, values: tuple[str, ...], name: str) -> CheckConstraint:
    """TEXT + CHECK instead of native enums, so a new state is a plain migration."""
    listed = ", ".join(f"'{v}'" for v in values)
    return CheckConstraint(f"{column} IN ({listed})", name=name)


ROLES = ("admin", "transporter", "factory", "buyer", "farmer")
USER_STATUSES = ("active", "pending", "suspended")
CALL_KINDS = ("intake", "verification")
LOT_STATUSES = ("open", "assigned", "rejected")
ESCALATION_STATUSES = ("open", "resolved")
JOB_STATES = (
    "created", "funded", "offered", "accepted", "picked_up", "delivered",
    "confirmed", "verified", "settled", "rejected", "disputed",
)
OFFER_STATUSES = ("pending", "accepted", "expired", "withdrawn")
PHOTO_KINDS = ("pickup", "delivery", "weighbridge")
LOCATION_KINDS = ("pickup", "delivery", "ping")
LEDGER_KINDS = (
    "escrow_in", "release_farmer", "release_transporter", "platform_fee", "refund",
    "release_factory", "release_ngo",  # product sales (FA3/B1)
)
SPLIT_PARTIES = ("farmer", "factory", "ngo", "platform")
PRODUCT_CATEGORIES = ("Clean Energy", "Farming & Garden", "Building Materials", "Home & Living")
ORDER_STATUSES = ("placed", "paid", "cancelled")
