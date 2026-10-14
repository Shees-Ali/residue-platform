import uuid

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.auth.firebase import AuthUser, as_admin
from app.db_models.tables import Factory, FactoryCandidate, Farmer, Job, Lot
from app.deps import DbSession, Events
from app.models.job import JobOut
from app.models.lot import AdminLotIn, LotOut, LotReadback, OverrideIn, RankingEntry
from app.services.assignment_store import assign_lot, override_factory
from app.services.job_views import job_out
from app.services.lot_store import create_lot_record

router = APIRouter(prefix="/api/lots", tags=["lots"])
admin_only = as_admin


def _lot_out(lot: Lot, job: Job | None) -> LotOut:
    return LotOut(
        id=str(lot.id),
        farmer_id=str(lot.farmer_id),
        residue_type=lot.residue_code,
        quantity_tonnes=float(lot.quantity_tonnes),
        lat=lot.lat,
        lon=lot.lon,
        status=lot.status,
        pickup_from=lot.pickup_from,
        pickup_to=lot.pickup_to,
        job_id=str(job.id) if job else None,
        job_state=job.state if job else None,
        created_at=lot.created_at,
    )


def _uuid(value: str, what: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except ValueError:
        raise HTTPException(404, f"Unknown {what}") from None


@router.get("", response_model=list[LotOut], dependencies=[admin_only])
async def list_lots(
    db: DbSession,
    status: str | None = None,
    farmer_id: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    query = select(Lot, Job).outerjoin(Job, Job.lot_id == Lot.id)
    if status:
        query = query.where(Lot.status == status)
    if farmer_id:
        query = query.where(Lot.farmer_id == _uuid(farmer_id, "farmer"))
    rows = (
        await db.execute(query.order_by(Lot.created_at.desc()).limit(limit).offset(offset))
    ).all()
    return [_lot_out(lot, job) for lot, job in rows]


@router.post("", response_model=LotReadback, status_code=201)
async def create_lot_for_farmer(
    db: DbSession,
    events: Events,
    body: AdminLotIn,
    user: AuthUser = admin_only,
):
    """Admin enters a lot by hand for a farmer (found or created by phone)."""
    await db.execute(
        insert(Farmer).values(phone=body.farmer_phone).on_conflict_do_nothing(
            index_elements=["phone"]
        )
    )
    farmer = (
        await db.execute(select(Farmer).where(Farmer.phone == body.farmer_phone))
    ).scalar_one()
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
    await db.commit()
    await events.publish("lot.created")
    if job:
        await events.publish("job.updated", str(job.id))
    return readback


@router.get("/{lot_id}", response_model=LotOut, dependencies=[admin_only])
async def get_lot(db: DbSession, lot_id: str):
    row = (
        await db.execute(
            select(Lot, Job).outerjoin(Job, Job.lot_id == Lot.id).where(
                Lot.id == _uuid(lot_id, "lot")
            )
        )
    ).first()
    if row is None:
        raise HTTPException(404, "Unknown lot")
    return _lot_out(*row)


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
    out = await job_out(db, job.id)
    await db.commit()
    await events.publish("job.updated", str(job.id))
    return out
