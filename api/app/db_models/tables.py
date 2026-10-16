"""PostgreSQL tables. Spec: memory/data-model.md. Money is BIGINT minor units, shares are bps."""
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db_models.base import (
    CALL_KINDS,
    ESCALATION_STATUSES,
    JOB_STATES,
    LEDGER_KINDS,
    LOCATION_KINDS,
    LOT_STATUSES,
    OFFER_STATUSES,
    ORDER_STATUSES,
    PHOTO_KINDS,
    PRODUCT_CATEGORIES,
    ROLES,
    SPLIT_PARTIES,
    USER_STATUSES,
    Base,
    created_at,
    one_of,
    updated_at,
    uuid_pk,
)

UUIDCol = UUID(as_uuid=True)
TS = DateTime(timezone=True)


def fk(target: str, **kw):
    return mapped_column(UUIDCol, ForeignKey(target), **kw)


def uid_fk(**kw):
    return mapped_column(Text, ForeignKey("users.uid"), **kw)


# --- people and places -------------------------------------------------------


class User(Base):
    __tablename__ = "users"
    __table_args__ = (one_of("role", ROLES, "role"), one_of("status", USER_STATUSES, "status"))
    uid: Mapped[str] = mapped_column(Text, primary_key=True)  # Firebase uid
    role: Mapped[str] = mapped_column(Text)
    # pending = signed up as transporter/factory, waiting for an admin; suspended = blocked
    status: Mapped[str] = mapped_column(Text, server_default=text("'active'"))
    email: Mapped[str | None] = mapped_column(Text, unique=True)
    display_name: Mapped[str] = mapped_column(Text, server_default=text("''"))
    phone: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = created_at()


class Village(Base):
    __tablename__ = "villages"
    __table_args__ = (UniqueConstraint("name", "district"),)
    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(Text)
    district: Mapped[str] = mapped_column(Text)
    lat: Mapped[float] = mapped_column(Float)
    lon: Mapped[float] = mapped_column(Float)


class ResidueType(Base):
    __tablename__ = "residue_types"
    code: Mapped[str] = mapped_column(Text, primary_key=True)
    label: Mapped[str] = mapped_column(Text)


class Farmer(Base):
    __tablename__ = "farmers"
    id: Mapped[uuid.UUID] = uuid_pk()
    user_uid: Mapped[str | None] = uid_fk(nullable=True, unique=True)  # dashboard login, if any
    phone: Mapped[str | None] = mapped_column(Text, unique=True)  # optional until SMS is required
    name: Mapped[str] = mapped_column(Text, server_default=text("''"))
    village_id: Mapped[uuid.UUID | None] = fk("villages.id", nullable=True)
    preferred_language: Mapped[str] = mapped_column(Text, server_default=text("'ur'"))
    created_at: Mapped[datetime] = created_at()


class Transporter(Base):
    __tablename__ = "transporters"
    __table_args__ = (CheckConstraint("max_tonnes > 0", name="max_tonnes_positive"),)
    id: Mapped[uuid.UUID] = uuid_pk()
    user_uid: Mapped[str | None] = uid_fk(nullable=True)
    phone: Mapped[str] = mapped_column(Text)
    tier: Mapped[int] = mapped_column(Integer, server_default=text("1"))  # approval tier
    max_tonnes: Mapped[Decimal] = mapped_column(Numeric(10, 2), server_default=text("5"))
    approved_at: Mapped[datetime | None] = mapped_column(TS)
    lat: Mapped[float] = mapped_column(Float)
    lon: Mapped[float] = mapped_column(Float)
    district: Mapped[str | None] = mapped_column(Text)  # the base as typed, for the edit form
    village: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime | None] = mapped_column(TS)


class Factory(Base):
    __tablename__ = "factories"
    __table_args__ = (CheckConstraint("price_per_tonne >= 0", name="price_nonneg"),)
    id: Mapped[uuid.UUID] = uuid_pk()
    user_uid: Mapped[str | None] = uid_fk(nullable=True)
    name: Mapped[str] = mapped_column(Text)
    lat: Mapped[float] = mapped_column(Float)
    lon: Mapped[float] = mapped_column(Float)
    price_per_tonne: Mapped[int] = mapped_column(BigInteger)  # minor units
    district: Mapped[str | None] = mapped_column(Text)
    village: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime | None] = mapped_column(TS)


class FactoryResidue(Base):
    __tablename__ = "factory_residues"
    factory_id: Mapped[uuid.UUID] = fk("factories.id", primary_key=True)
    residue_code: Mapped[str] = mapped_column(
        Text, ForeignKey("residue_types.code"), primary_key=True
    )


# --- intake ------------------------------------------------------------------


class Call(Base):
    """Call record: the API resolves the farmer from here, never from request fields."""

    __tablename__ = "calls"
    __table_args__ = (one_of("kind", CALL_KINDS, "kind"),)
    id: Mapped[uuid.UUID] = uuid_pk()
    twilio_call_sid: Mapped[str | None] = mapped_column(Text, unique=True)
    farmer_id: Mapped[uuid.UUID | None] = fk("farmers.id", nullable=True)
    kind: Mapped[str] = mapped_column(Text, server_default=text("'intake'"))
    status: Mapped[str] = mapped_column(Text, server_default=text("'in_progress'"))
    transcript: Mapped[str] = mapped_column(Text, server_default=text("''"))
    summary: Mapped[str] = mapped_column(Text, server_default=text("''"))
    started_at: Mapped[datetime] = created_at()


class Lot(Base):
    __tablename__ = "lots"
    __table_args__ = (
        one_of("status", LOT_STATUSES, "status"),
        CheckConstraint("quantity_tonnes > 0", name="quantity_positive"),
    )
    id: Mapped[uuid.UUID] = uuid_pk()
    farmer_id: Mapped[uuid.UUID] = fk("farmers.id")
    call_id: Mapped[uuid.UUID | None] = fk("calls.id", nullable=True)
    residue_code: Mapped[str] = mapped_column(Text, ForeignKey("residue_types.code"))
    quantity_tonnes: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    pickup_from: Mapped[datetime | None] = mapped_column(TS)
    pickup_to: Mapped[datetime | None] = mapped_column(TS)
    village_id: Mapped[uuid.UUID | None] = fk("villages.id", nullable=True)
    village_name: Mapped[str | None] = mapped_column(Text)  # as reported (or the matched village)
    district: Mapped[str | None] = mapped_column(Text)
    place_match: Mapped[str | None] = mapped_column(Text)  # exact | fuzzy | district
    lat: Mapped[float] = mapped_column(Float)
    lon: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(Text, server_default=text("'open'"))
    created_at: Mapped[datetime] = created_at()


class FactoryCandidate(Base):
    """A1 ranked list plus the admin override log."""

    __tablename__ = "factory_candidates"
    __table_args__ = (UniqueConstraint("lot_id", "factory_id"),)
    id: Mapped[uuid.UUID] = uuid_pk()
    lot_id: Mapped[uuid.UUID] = fk("lots.id")
    factory_id: Mapped[uuid.UUID] = fk("factories.id")
    rank: Mapped[int] = mapped_column(Integer)
    score: Mapped[float] = mapped_column(Float)
    distance_km: Mapped[float] = mapped_column(Float)
    price_per_tonne: Mapped[int] = mapped_column(BigInteger)
    chosen: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    overridden_by_uid: Mapped[str | None] = uid_fk(nullable=True)
    override_reason: Mapped[str | None] = mapped_column(Text)


class Escalation(Base):
    __tablename__ = "escalations"
    __table_args__ = (one_of("status", ESCALATION_STATUSES, "status"),)
    id: Mapped[uuid.UUID] = uuid_pk()
    call_id: Mapped[uuid.UUID | None] = fk("calls.id", nullable=True)  # none for a web dispute
    job_id: Mapped[uuid.UUID | None] = fk("jobs.id", nullable=True)
    summary: Mapped[str] = mapped_column(Text)
    transcript: Mapped[str] = mapped_column(Text, server_default=text("''"))
    status: Mapped[str] = mapped_column(Text, server_default=text("'open'"))
    resolved_by_uid: Mapped[str | None] = uid_fk(nullable=True)
    created_at: Mapped[datetime] = created_at()


# --- dispatch and delivery ---------------------------------------------------


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (
        one_of("state", JOB_STATES, "state"),
        CheckConstraint("farmer_share_bps BETWEEN 0 AND 10000", name="share_bps_range"),
    )
    id: Mapped[uuid.UUID] = uuid_pk()
    lot_id: Mapped[uuid.UUID] = fk("lots.id", unique=True)  # one lot per job
    factory_id: Mapped[uuid.UUID] = fk("factories.id")
    transporter_id: Mapped[uuid.UUID | None] = fk("transporters.id", nullable=True)
    state: Mapped[str] = mapped_column(Text, server_default=text("'created'"))
    quoted_price_per_tonne: Mapped[int] = mapped_column(BigInteger)
    farmer_share_bps: Mapped[int] = mapped_column(Integer)
    est_weight_kg: Mapped[int] = mapped_column(Integer)
    final_weight_kg: Mapped[int | None] = mapped_column(Integer)
    rejection_reason: Mapped[str | None] = mapped_column(Text)
    funded_at: Mapped[datetime | None] = mapped_column(TS)
    accepted_at: Mapped[datetime | None] = mapped_column(TS)
    picked_up_at: Mapped[datetime | None] = mapped_column(TS)
    delivered_at: Mapped[datetime | None] = mapped_column(TS)
    confirmed_at: Mapped[datetime | None] = mapped_column(TS)
    verified_at: Mapped[datetime | None] = mapped_column(TS)
    settled_at: Mapped[datetime | None] = mapped_column(TS)
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = updated_at()


class Offer(Base):
    __tablename__ = "offers"
    __table_args__ = (
        one_of("status", OFFER_STATUSES, "status"),
        UniqueConstraint("job_id", "sequence"),
        CheckConstraint("payout_amount >= 0", name="payout_nonneg"),
        # at most one accepted offer per job: the T1 "single winner" backstop
        Index(
            "uq_offers_one_accepted",
            "job_id",
            unique=True,
            postgresql_where=text("status = 'accepted'"),
        ),
    )
    id: Mapped[uuid.UUID] = uuid_pk()
    job_id: Mapped[uuid.UUID] = fk("jobs.id")
    transporter_id: Mapped[uuid.UUID] = fk("transporters.id")
    sequence: Mapped[int] = mapped_column(Integer)
    expires_at: Mapped[datetime] = mapped_column(TS)
    status: Mapped[str] = mapped_column(Text, server_default=text("'pending'"))
    payout_amount: Mapped[int] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = created_at()


class Photo(Base):
    __tablename__ = "photos"
    __table_args__ = (one_of("kind", PHOTO_KINDS, "kind"),)
    id: Mapped[uuid.UUID] = uuid_pk()
    job_id: Mapped[uuid.UUID] = fk("jobs.id")
    kind: Mapped[str] = mapped_column(Text)
    storage_path: Mapped[str] = mapped_column(Text)
    uploaded_by_uid: Mapped[str | None] = uid_fk(nullable=True)
    weight_kg: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = created_at()


class JobLocation(Base):
    """Where the transporter was: at pickup, at delivery, and pings while on the way."""

    __tablename__ = "job_locations"
    __table_args__ = (
        one_of("kind", LOCATION_KINDS, "kind"),
        Index("ix_job_locations_job_id_recorded_at", "job_id", "recorded_at"),
    )
    id: Mapped[uuid.UUID] = uuid_pk()
    job_id: Mapped[uuid.UUID] = fk("jobs.id")
    transporter_id: Mapped[uuid.UUID] = fk("transporters.id")
    kind: Mapped[str] = mapped_column(Text)
    lat: Mapped[float] = mapped_column(Float)
    lon: Mapped[float] = mapped_column(Float)
    accuracy_m: Mapped[float | None] = mapped_column(Float)
    # pickup: metres from the farm; delivery: metres from the factory. Stored, never blocking.
    distance_from_target_m: Mapped[int | None] = mapped_column(Integer)
    recorded_at: Mapped[datetime] = mapped_column(TS, server_default=func.now())


class Grade(Base):
    """AI visual estimate only; the weighbridge confirmation is authoritative."""

    __tablename__ = "grades"
    __table_args__ = (CheckConstraint("is_estimate", name="always_estimate"),)
    id: Mapped[uuid.UUID] = uuid_pk()
    photo_id: Mapped[uuid.UUID] = fk("photos.id")
    residue_code: Mapped[str | None] = mapped_column(Text, ForeignKey("residue_types.code"))
    moisture_band: Mapped[str | None] = mapped_column(Text)
    contamination_flags: Mapped[list] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    confidence: Mapped[float] = mapped_column(Float)
    is_estimate: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    created_at: Mapped[datetime] = created_at()


class Verification(Base):
    __tablename__ = "verifications"
    id: Mapped[uuid.UUID] = uuid_pk()
    job_id: Mapped[uuid.UUID] = fk("jobs.id")
    call_id: Mapped[uuid.UUID | None] = fk("calls.id", nullable=True)
    confirmed: Mapped[bool] = mapped_column(Boolean)
    note: Mapped[str] = mapped_column(Text, server_default=text("''"))
    created_at: Mapped[datetime] = created_at()


# --- money -------------------------------------------------------------------


class Product(Base):
    __tablename__ = "products"
    __table_args__ = (
        CheckConstraint("stock >= 0", name="stock_nonneg"),
        CheckConstraint("unit_price >= 0", name="price_nonneg"),
        one_of("category", PRODUCT_CATEGORIES, "category"),
    )
    id: Mapped[uuid.UUID] = uuid_pk()
    factory_id: Mapped[uuid.UUID] = fk("factories.id")
    name: Mapped[str] = mapped_column(Text)
    unit_price: Mapped[int] = mapped_column(BigInteger)
    stock: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    category: Mapped[str] = mapped_column(Text, server_default=text("'Clean Energy'"))
    unit: Mapped[str] = mapped_column(Text, server_default=text("'per 25 kg bag'"))
    description: Mapped[str] = mapped_column(Text, server_default=text("''"))
    active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    created_at: Mapped[datetime] = created_at()


class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (
        one_of("status", ORDER_STATUSES, "status"),
        CheckConstraint("quantity > 0", name="quantity_positive"),
        CheckConstraint("total >= 0", name="total_nonneg"),
    )
    id: Mapped[uuid.UUID] = uuid_pk()
    buyer_uid: Mapped[str] = uid_fk()
    product_id: Mapped[uuid.UUID] = fk("products.id")
    quantity: Mapped[int] = mapped_column(Integer)
    total: Mapped[int] = mapped_column(BigInteger)
    status: Mapped[str] = mapped_column(Text, server_default=text("'placed'"))
    created_at: Mapped[datetime] = created_at()


class SaleSplit(Base):
    """FA3 four-way split. Shares per order sum to 10000 bps (revenue_share + test)."""

    __tablename__ = "sale_splits"
    __table_args__ = (
        one_of("party", SPLIT_PARTIES, "party"),
        UniqueConstraint("order_id", "party"),
        CheckConstraint("share_bps BETWEEN 0 AND 10000", name="share_bps_range"),
        CheckConstraint("amount >= 0", name="amount_nonneg"),
    )
    id: Mapped[uuid.UUID] = uuid_pk()
    order_id: Mapped[uuid.UUID] = fk("orders.id")
    party: Mapped[str] = mapped_column(Text)
    share_bps: Mapped[int] = mapped_column(Integer)
    amount: Mapped[int] = mapped_column(BigInteger)


class LedgerEntry(Base):
    """Append-only: app code inserts, never updates or deletes."""

    __tablename__ = "ledger_entries"
    __table_args__ = (
        one_of("kind", LEDGER_KINDS, "kind"),
        CheckConstraint("amount >= 0", name="amount_nonneg"),
        CheckConstraint("job_id IS NOT NULL OR order_id IS NOT NULL", name="has_subject"),
    )
    id: Mapped[uuid.UUID] = uuid_pk()
    job_id: Mapped[uuid.UUID | None] = fk("jobs.id", nullable=True, index=True)
    order_id: Mapped[uuid.UUID | None] = fk("orders.id", nullable=True)
    kind: Mapped[str] = mapped_column(Text)
    amount: Mapped[int] = mapped_column(BigInteger)  # minor units
    party_uid: Mapped[str | None] = uid_fk(nullable=True)
    created_at: Mapped[datetime] = created_at()


# --- plumbing ----------------------------------------------------------------


class IdempotencyKey(Base):
    __tablename__ = "idempotency_keys"
    key: Mapped[str] = mapped_column(Text, primary_key=True)
    route: Mapped[str] = mapped_column(Text)
    response_hash: Mapped[str | None] = mapped_column(Text)
    request_hash: Mapped[str | None] = mapped_column(Text)
    status_code: Mapped[int | None] = mapped_column(Integer)
    response: Mapped[dict | None] = mapped_column(JSONB)  # NULL while the first request runs
    created_at: Mapped[datetime] = created_at()


# --- events and notifications (EV1 to EV7) ---------------------------------------------


class Event(Base):
    """An immutable business fact: what happened, to which job, and who did it."""

    __tablename__ = "events"
    __table_args__ = (Index("ix_events_job_id_created_at", "job_id", "created_at"),)
    id: Mapped[uuid.UUID] = uuid_pk()
    type: Mapped[str] = mapped_column(Text)
    job_id: Mapped[uuid.UUID | None] = fk("jobs.id", nullable=True)
    lot_id: Mapped[uuid.UUID | None] = fk("lots.id", nullable=True)
    order_id: Mapped[uuid.UUID | None] = fk("orders.id", nullable=True)
    actor_uid: Mapped[str | None] = uid_fk(nullable=True)
    actor_role: Mapped[str | None] = mapped_column(Text)
    summary: Mapped[str] = mapped_column(Text)  # neutral one line for the job timeline
    data: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    visible_to: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default=text("'{}'"))
    created_at: Mapped[datetime] = created_at()


class Notification(Base):
    """One person's copy of an event: ready-to-show text, read state, delivery state."""

    __tablename__ = "notifications"
    __table_args__ = (
        Index(
            "uq_notifications_event_recipient_uid",
            "event_id",
            "recipient_uid",
            unique=True,
            postgresql_where=text("recipient_uid IS NOT NULL"),
        ),
        Index(
            "uq_notifications_event_recipient_farmer",
            "event_id",
            "recipient_farmer_id",
            unique=True,
            postgresql_where=text("recipient_farmer_id IS NOT NULL"),
        ),
        Index("ix_notifications_recipient_uid_created_at", "recipient_uid", "created_at"),
        Index(
            "ix_notifications_undelivered",
            "created_at",
            postgresql_where=text("delivered_at IS NULL AND recipient_uid IS NOT NULL"),
        ),
    )
    id: Mapped[uuid.UUID] = uuid_pk()
    event_id: Mapped[uuid.UUID] = fk("events.id")
    recipient_uid: Mapped[str | None] = uid_fk(nullable=True)
    # a farmer who only phones has no login: kept for a future SMS or voice channel
    recipient_farmer_id: Mapped[uuid.UUID | None] = fk("farmers.id", nullable=True)
    type: Mapped[str] = mapped_column(Text)
    level: Mapped[str] = mapped_column(Text, server_default=text("'info'"))
    title: Mapped[str] = mapped_column(Text)
    body: Mapped[str] = mapped_column(Text)
    refresh: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default=text("'{}'"))
    job_id: Mapped[uuid.UUID | None] = fk("jobs.id", nullable=True)
    created_at: Mapped[datetime] = created_at()
    read_at: Mapped[datetime | None] = mapped_column(TS)
    delivered_at: Mapped[datetime | None] = mapped_column(TS)
