import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.auth.firebase import AuthUser, as_admin, as_farmer, require_role
from app.auth.idempotency import require_idempotency_key
from app.db_models.tables import Factory, FactoryCandidate, Farmer, Lot, User
from app.deps import DbSession, Events
from app.models.job import JobOut
from app.models.lot import (
    AdminLotIn,
    LotOut,
    LotReadback,
    MineLotIn,
    OverrideIn,
    RankingEntry,
)
from app.services.assignment_store import assign_lot, override_factory
from app.services.idempotency import request_hash, run_idempotent
from app.services.job_views import Viewer, job_out
from app.services.lot_errors import as_field_errors
from app.services.lot_store import create_lot_record
from app.services.lot_views import get_lot_out, lot_out, lot_query
from app.services.lots import LotError
from app.services.registration import ensure_farmer

router = APIRouter(prefix="/api/lots", tags=["lots"])
admin_only = as_admin
admin_or_farmer = Depends(require_role("admin", "farmer"))


def _uuid(value: str, what: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except ValueError:
        raise HTTPException(404, f"Unknown {what}") from None


@router.get("", response_model=list[LotOut])
async def list_lots(
    db: DbSession,
    status: Literal["open", "assigned", "rejected"] | None = None,
    farmer_id: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: AuthUser = admin_or_farmer,
):
    """Admin: every lot. Farmer: only their own (matched through their verified phone)."""
    query = lot_query()
    if user.role == "farmer":
        query = query.where(Farmer.user_uid == user.uid)
    if status:
        query = query.where(Lot.status == status)
    if farmer_id:
        query = query.where(Lot.farmer_id == _uuid(farmer_id, "farmer"))
    rows = (
        await db.execute(query.order_by(Lot.created_at.desc()).limit(limit).offset(offset))
    ).all()
    return [lot_out(row) for row in rows]


@router.post("", response_model=LotReadback, status_code=201)
async def create_lot_for_farmer(
    db: DbSession,
    events: Events,
    body: AdminLotIn,
    user: AuthUser = admin_only,
):
    """Admin enters a lot by hand for a farmer (found or created by phone)."""
    await db.execute(
        insert(Farmer).values(phone=body.farmer_phone, name=body.farmer_name or "")
        .on_conflict_do_nothing(index_elements=["phone"])
    )
    farmer = (
        await db.execute(select(Farmer).where(Farmer.phone == body.farmer_phone))
    ).scalar_one()
    if body.farmer_name and not farmer.name:
        farmer.name = body.farmer_name
    try:
        async with db.begin_nested():  # a rejected entry leaves nothing behind
            readback = await create_lot_record(
                db,
                farmer_id=farmer.id,
                call_id=None,
                residue_type=body.residue_type,
                quantity_tonnes=body.quantity_tonnes,
                pickup_date=body.pickup_date,
                pickup_part=body.pickup_part,
                village=body.village,
                district=body.district,
            )
    except LotError as e:
        raise as_field_errors(e) from None
    job = await assign_lot(db, uuid.UUID(readback.lot_id))
    await db.commit()
    await events.publish("lot.created")
    if job:
        await events.publish("job.updated", str(job.id))
    return readback


@router.post("/mine", response_model=LotOut, status_code=201)
async def create_my_lot(
    db: DbSession,
    events: Events,
    body: MineLotIn,
    user: AuthUser = as_farmer,
    key: str = Depends(require_idempotency_key),
):
    """A farmer reports their own residue on the web. Same checks and assignment as a phone call.

    A double click or a retry with the same Idempotency-Key returns the same lot.
    """
    account = await db.get(User, user.uid)
    farmer = await ensure_farmer(db, account) if account else None
    if farmer is None:
        raise HTTPException(
            409,
            {
                "code": "phone_not_verified",
                "message": "Verify your phone number to report residue",
            },
        )
    assigned_job: list[str] = []

    async def work() -> tuple[int, dict]:
        readback = await create_lot_record(
            db,
            farmer_id=farmer.id,
            call_id=None,
            residue_type=body.residue_type,
            quantity_tonnes=body.quantity_tonnes,
            pickup_date=body.pickup_date,
            pickup_part=body.pickup_part,
            village=body.village,
            district=body.district,
        )
        job = await assign_lot(db, uuid.UUID(readback.lot_id))
        if job is not None:
            assigned_job.append(str(job.id))
        out = await get_lot_out(db, uuid.UUID(readback.lot_id))
        return 201, out.model_dump(mode="json")  # type: ignore[union-attr]

    try:
        # a rejected entry rolls the idempotency key back too, so the person can fix and resend
        async with db.begin_nested():
            _, payload, replayed = await run_idempotent(
                db,
                f"{user.uid}:{key}",
                "POST /api/lots/mine",
                request_hash(body.model_dump()),
                work,
            )
    except LotError as e:
        raise as_field_errors(e) from None
    await db.commit()
    if not replayed:
        await events.publish("lot.created")
        for job_id in assigned_job:
            await events.publish("job.updated", job_id)
    return payload


@router.get("/{lot_id}", response_model=LotOut)
async def get_lot(db: DbSession, lot_id: str, user: AuthUser = admin_or_farmer):
    query = lot_query().where(Lot.id == _uuid(lot_id, "lot"))
    if user.role == "farmer":  # someone else's lot looks like a missing one
        query = query.where(Farmer.user_uid == user.uid)
    row = (await db.execute(query)).first()
    if row is None:
        raise HTTPException(404, "Unknown lot")
    return lot_out(row)


@router.get("/{lot_id}/ranking", response_model=list[RankingEntry], dependencies=[admin_only])
async def get_ranking(db: DbSession, lot_id: str):
    rows = (
        await db.execute(
            select(FactoryCandidate, Factory.name)
            .join(Factory, Factory.id == FactoryCandidate.factory_id)
            .where(FactoryCandidate.lot_id == _uuid(lot_id, "lot"))
            .order_by(FactoryCandidate.rank)
        )
    ).all()
    return [
        RankingEntry(
            factory_id=str(c.factory_id),
            factory_name=name,
            rank=c.rank,
            score=c.score,
            distance_km=c.distance_km,
            price_per_tonne=c.price_per_tonne,
            chosen=c.chosen,
            override_reason=c.override_reason,
        )
        for c, name in rows
    ]


@router.post("/{lot_id}/override", response_model=JobOut)
async def override(
    db: DbSession,
    events: Events,
    lot_id: str,
    body: OverrideIn,
    user: AuthUser = admin_only,
):
    job = await override_factory(
        db, _uuid(lot_id, "lot"), _uuid(body.factory_id, "factory"), user.uid, body.reason
    )
    out = await job_out(db, job.id, Viewer("admin"))
    await db.commit()
    await events.publish("job.updated", str(job.id))
    return out

