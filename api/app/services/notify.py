"""Record business facts and tell the people who need to know (EV1, EV2).

`emit` runs inside the caller's transaction, next to the change it describes, so a refused or
rolled-back action leaves no event behind. Delivery to Firestore happens after the commit
(`inbox.py`); the notification ids waiting for it ride on the session (`db.info`).
"""
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db_models.tables import (
    Event,
    Factory,
    Farmer,
    Job,
    Lot,
    Notification,
    Order,
    Product,
    ResidueType,
    Transporter,
    User,
)
from app.services.notify_catalog import CATALOG, kg, pkr, render, summary, tonnes

PENDING_KEY = "notification_ids"


@dataclass(frozen=True)
class Recipient:
    uid: str | None = None
    farmer_id: uuid.UUID | None = None


@dataclass
class Context:
    """Everything the templates and the audiences need, loaded once per event."""

    values: dict[str, Any] = field(default_factory=dict)
    audiences: dict[str, list[Recipient]] = field(default_factory=dict)


def _json(value: Any) -> Any:
    return str(value) if isinstance(value, uuid.UUID) else value


async def _admins(db: AsyncSession) -> list[Recipient]:
    uids = (
        await db.execute(select(User.uid).where(User.role == "admin", User.status == "active"))
    ).scalars().all()
    return [Recipient(uid=u) for u in uids]


async def _transporter_recipient(db: AsyncSession, transporter_id: Any) -> list[Recipient]:
    if not transporter_id:
        return []
    uid = (
        await db.execute(
            select(Transporter.user_uid).where(Transporter.id == uuid.UUID(str(transporter_id)))
        )
    ).scalar_one_or_none()
    return [Recipient(uid=uid)] if uid else []


async def _factory_recipient(db: AsyncSession, factory: Factory | None) -> list[Recipient]:
    return [Recipient(uid=factory.user_uid)] if factory is not None and factory.user_uid else []


def _farmer_recipient(farmer: Farmer | None) -> list[Recipient]:
    if farmer is None:
        return []
    # a farmer who only phones has no login: the row waits for a future SMS or voice channel
    return [Recipient(uid=farmer.user_uid)] if farmer.user_uid else [Recipient(farmer_id=farmer.id)]


async def _lot_values(db: AsyncSession, lot: Lot) -> dict[str, Any]:
    label = (await db.get(ResidueType, lot.residue_code)).label
    return {
        "tonnes": tonnes(float(lot.quantity_tonnes)),
        "residue": label.lower(),
        "where": lot.village_name or lot.district or "your area",
    }


async def build_context(
    db: AsyncSession,
    *,
    job_id: uuid.UUID | None,
    lot_id: uuid.UUID | None,
    order_id: uuid.UUID | None,
    data: dict[str, Any],
) -> Context:
    ctx = Context()
    v = ctx.values
    job: Job | None = None
    lot: Lot | None = None
    factory: Factory | None = None
    if job_id is not None:
        job = await db.get(Job, job_id)
        lot = await db.get(Lot, job.lot_id)
        factory = await db.get(Factory, job.factory_id)
    elif lot_id is not None:
        lot = await db.get(Lot, lot_id)
    if factory is None and data.get("factory_id"):
        factory = await db.get(Factory, uuid.UUID(str(data["factory_id"])))

    if lot is not None:
        v.update(await _lot_values(db, lot))
        farmer = await db.get(Farmer, lot.farmer_id)
        ctx.audiences["farmer"] = _farmer_recipient(farmer)
    if factory is not None:
        v["factory"] = factory.name
        ctx.audiences["factory"] = await _factory_recipient(db, factory)
    if job is not None:
        if job.final_weight_kg:
            v["weight"] = kg(job.final_weight_kg)
        ctx.audiences["transporter"] = await _transporter_recipient(db, job.transporter_id)
    if data.get("weight_kg"):
        v["weight"] = kg(data["weight_kg"])
    if data.get("old_factory_id"):
        old = await db.get(Factory, uuid.UUID(str(data["old_factory_id"])))
        ctx.audiences["old_factory"] = await _factory_recipient(db, old)
    if data.get("transporter_id"):
        ctx.audiences["offered"] = await _transporter_recipient(db, data["transporter_id"])
    if data.get("uid"):
        ctx.audiences["owner"] = [Recipient(uid=str(data["uid"]))]

    if order_id is not None:
        order = await db.get(Order, order_id)
        product = await db.get(Product, order.product_id)
        seller = await db.get(Factory, product.factory_id)
        v.update(product=product.name, quantity=order.quantity, amount=pkr(order.total))
        ctx.audiences["buyer"] = [Recipient(uid=order.buyer_uid)]
        ctx.audiences["seller"] = await _factory_recipient(db, seller)

    for key in ("amount", "farmer_amount", "transporter_amount"):
        if data.get(key) is not None:
            v[key] = pkr(data[key])
    for key in ("minutes", "km", "count", "stock", "role", "tier", "product"):
        if data.get(key) is not None:
            v[key] = data[key]
    if data.get("max_tonnes") is not None:
        v["max_tonnes"] = f"{float(data['max_tonnes']):g}"
    ctx.audiences["admins"] = await _admins(db)
    return ctx


async def emit(
    db: AsyncSession,
    type: str,
    *,
    job_id: uuid.UUID | str | None = None,
    lot_id: uuid.UUID | str | None = None,
    order_id: uuid.UUID | str | None = None,
    actor: Any = None,
    include_actor: bool = False,
    **data: Any,
) -> Event:
    """Write the event and one notification per person who should hear about it.

    `actor` (anything with `.uid` and `.role`) is the person who did it. They are not notified of
    their own action unless `include_actor` is set (money results belong in their bell).
    `data` carries ids and amounts, never free text: it is stored on the event and read by the
    templates.
    """
    spec = CATALOG[type]
    job_key = uuid.UUID(str(job_id)) if job_id else None
    lot_key = uuid.UUID(str(lot_id)) if lot_id else None
    order_key = uuid.UUID(str(order_id)) if order_id else None
    ctx = await build_context(db, job_id=job_key, lot_id=lot_key, order_id=order_key, data=data)
    if job_key is not None and lot_key is None:
        lot_key = (await db.get(Job, job_key)).lot_id

    actor_uid = getattr(actor, "uid", None)
    event = Event(
        type=type,
        job_id=job_key,
        lot_id=lot_key,
        order_id=order_key,
        actor_uid=actor_uid if actor_uid and await db.get(User, actor_uid) else None,
        actor_role=getattr(actor, "role", None),
        summary=summary(type, ctx.values),
        created_at=now(),  # not the transaction start: events of one request stay in order
        data={k: _json(v) for k, v in data.items()},
        visible_to=list(spec.visible_to),
    )
    db.add(event)
    await db.flush()

    seen: set[tuple[str | None, uuid.UUID | None]] = set()
    created: list[uuid.UUID] = []
    for audience in spec.messages:
        message = render(type, audience, ctx.values)
        for who in ctx.audiences.get(audience, []):
            key = (who.uid, who.farmer_id)
            if key in seen or (not include_actor and who.uid is not None and who.uid == actor_uid):
                continue
            seen.add(key)
            row = Notification(
                event_id=event.id,
                recipient_uid=who.uid,
                recipient_farmer_id=who.farmer_id,
                type=type,
                level=spec.level,
                title=message.title,
                body=message.body,
                refresh=list(spec.refresh),
                job_id=job_key,
                created_at=now(),
            )
            db.add(row)
            await db.flush()
            created.append(row.id)
    db.info.setdefault(PENDING_KEY, []).extend(created)
    return event


def now() -> datetime:
    return datetime.now(UTC)


ALERT_EVERY = timedelta(hours=6)


async def alert_unbalanced_ledger(db: AsyncSession) -> bool:
    """Tell the admins when the ledger check fails, at most once every few hours."""
    from app.services.reports import ledger_check

    check = await ledger_check(db)
    if check.balanced:
        return False
    recent = (
        await db.execute(
            select(Event.id)
            .where(Event.type == "ledger.unbalanced", Event.created_at > now() - ALERT_EVERY)
            .limit(1)
        )
    ).first()
    if recent is not None:
        return False
    count = len(check.unbalanced_jobs) + len(check.unbalanced_orders)
    await emit(db, "ledger.unbalanced", count=count)
    return True
