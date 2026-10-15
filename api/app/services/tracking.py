"""Where the load is: the track, the next stop and a rough arrival time."""
import math
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db_models.tables import Factory, Job, JobLocation, Lot
from app.models.delivery import PingIn
from app.models.tracking import ActiveTrack, Place, TrackOut, TrackPoint
from app.services.assignment import haversine_km

ASSUMED_KMH = 40  # straight line at an assumed speed: an estimate, shown as "about"
PING_GAP = timedelta(seconds=5)  # pings closer than this are dropped
MOVING = ("accepted", "picked_up")


def _point(row: JobLocation) -> TrackPoint:
    return TrackPoint(
        kind=row.kind,
        lat=row.lat,
        lon=row.lon,
        at=row.recorded_at,
        accuracy_m=row.accuracy_m,
        distance_from_target_m=row.distance_from_target_m,
    )


def next_stop(state: str) -> str | None:
    """Heading to the farm until the pickup is recorded, then to the factory."""
    return {"accepted": "pickup", "picked_up": "factory"}.get(state)


def eta_for(
    last: TrackPoint | None, target: Place | None
) -> tuple[float | None, int | None]:
    """(km, minutes) from the last position to the next stop."""
    if last is None or target is None:
        return None, None
    km = haversine_km(last.lat, last.lon, target.lat, target.lon)
    return round(km, 1), max(1, math.ceil(km / ASSUMED_KMH * 60))


async def record_ping(
    db: AsyncSession, job: Job, body: PingIn, now: datetime | None = None
) -> bool:
    """Store a position unless one arrived in the last few seconds. Returns whether it was kept."""
    now = now or datetime.now(UTC)
    last = (
        await db.execute(
            select(JobLocation.recorded_at)
            .where(JobLocation.job_id == job.id)
            .order_by(JobLocation.recorded_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if last is not None and now - last < PING_GAP:
        return False
    db.add(
        JobLocation(
            job_id=job.id,
            transporter_id=job.transporter_id,
            kind="ping",
            lat=body.lat,
            lon=body.lon,
            accuracy_m=body.accuracy_m,
            recorded_at=now,
        )
    )
    await db.flush()
    return True


async def track_for(db: AsyncSession, job: Job) -> TrackOut:
    lot = await db.get(Lot, job.lot_id)
    factory = await db.get(Factory, job.factory_id)
    rows = (
        await db.execute(
            select(JobLocation)
            .where(JobLocation.job_id == job.id)
            .order_by(JobLocation.recorded_at)
        )
    ).scalars().all()
    points = [_point(r) for r in rows]
    last = points[-1] if points else None
    pickup = Place(lat=lot.lat, lon=lot.lon, name=lot.village_name)
    dest = Place(lat=factory.lat, lon=factory.lon, name=factory.name)
    heading = next_stop(job.state)
    km, eta = eta_for(last, {"pickup": pickup, "factory": dest}.get(heading or ""))
    by_kind = {r.kind: r.distance_from_target_m for r in rows if r.kind != "ping"}
    return TrackOut(
        job_id=str(job.id),
        state=job.state,
        pickup=pickup,
        factory=dest,
        points=points,
        last=last,
        heading_to=heading,
        distance_to_target_km=km,
        eta_minutes=eta,
        pickup_off_site_m=by_kind.get("pickup"),
        delivery_off_site_m=by_kind.get("delivery"),
    )


async def active_tracks(
    db: AsyncSession, factory_id: uuid.UUID | None = None
) -> list[ActiveTrack]:
    """One row per job that is on the move, with its last known position."""
    query = (
        select(Job, Lot, Factory)
        .join(Lot, Lot.id == Job.lot_id)
        .join(Factory, Factory.id == Job.factory_id)
        .where(Job.state.in_(MOVING))
        .order_by(Job.created_at.desc())
    )
    if factory_id:
        query = query.where(Job.factory_id == factory_id)
    out = []
    for job, lot, factory in (await db.execute(query)).all():
        last_row = (
            await db.execute(
                select(JobLocation)
                .where(JobLocation.job_id == job.id)
                .order_by(JobLocation.recorded_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        last = _point(last_row) if last_row else None
        pickup = Place(lat=lot.lat, lon=lot.lon, name=lot.village_name)
        dest = Place(lat=factory.lat, lon=factory.lon, name=factory.name)
        heading = next_stop(job.state)
        km, eta = eta_for(last, {"pickup": pickup, "factory": dest}.get(heading or ""))
        out.append(
            ActiveTrack(
                job_id=str(job.id),
                state=job.state,
                residue_type=lot.residue_code,
                quantity_tonnes=float(lot.quantity_tonnes),
                village=lot.village_name,
                factory_name=factory.name,
                pickup=pickup,
                factory=dest,
                last=last,
                heading_to=heading,
                distance_to_target_km=km,
                eta_minutes=eta,
            )
        )
    return out
