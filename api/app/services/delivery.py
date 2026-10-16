"""T2: the transporter proves pickup and delivery with a photo, a weight and a place."""
from datetime import UTC, datetime
from types import SimpleNamespace

from sqlalchemy.ext.asyncio import AsyncSession

from app.db_models.tables import Factory, Job, JobLocation, Lot, Photo
from app.models.delivery import LegIn
from app.services.assignment import haversine_km
from app.services.job_flow import transition
from app.services.notify import emit
from app.services.storage import PHOTO_MAX_BYTES, Storage, photo_prefix
from app.validation import FieldErrors

MAX_WEIGHT_KG = 100_000
FAR_METERS = 25_000  # a step recorded this far from where it belongs is flagged for the admin
WEIGHT_HELP = "Weight must be a whole number of kilograms between 1 and 100,000"
PHOTO_HELP = "Add a photo (JPEG, PNG or WebP, up to 5 MB)"

# kind -> (state before, state after, timestamp column)
LEGS = {
    "pickup": ("accepted", "picked_up", "picked_up_at"),
    "delivery": ("picked_up", "delivered", "delivered_at"),
}


def check_photo_path(job_id: str, kind: str, path: str) -> None:
    if not path.startswith(photo_prefix(job_id, kind)):
        raise FieldErrors(
            [("photo_path", f"That photo is not an upload for this {kind} step. {PHOTO_HELP}")],
            code="wrong_photo",
        )


async def check_photo_uploaded(storage: Storage, path: str) -> None:
    """The file must really be there, not empty and not over 5 MB."""
    size = await storage.size(path)
    if size is None:
        raise FieldErrors([("photo_path", "Upload the photo first")], code="not_uploaded")
    if size == 0:
        raise FieldErrors([("photo_path", "The photo file is empty")], code="empty_photo")
    if size > PHOTO_MAX_BYTES:
        raise FieldErrors([("photo_path", "Photo must be 5 MB or smaller")], code="photo_too_big")


def check_weight(weight_kg: int, field: str = "weight_kg") -> None:
    if not isinstance(weight_kg, int) or isinstance(weight_kg, bool) or not (
        0 < weight_kg <= MAX_WEIGHT_KG
    ):
        raise FieldErrors([(field, WEIGHT_HELP)], code="invalid_weight")


async def record_leg(
    db: AsyncSession,
    job: Job,
    kind: str,
    uid: str,
    body: LegIn,
    storage: Storage,
    now: datetime | None = None,
) -> None:
    """Move accepted -> picked_up or picked_up -> delivered, storing the photo, weight and place.

    How far the transporter was from the farm (pickup) or the factory (delivery) is stored for
    the admin; it never blocks the step.
    """
    check_photo_path(str(job.id), kind, body.photo_path)
    await check_photo_uploaded(storage, body.photo_path)
    check_weight(body.weight_kg)
    before, after, column = LEGS[kind]
    stamp = now or datetime.now(UTC)
    await transition(db, job.id, before, after, **{column: stamp})
    db.add(
        Photo(
            job_id=job.id,
            kind=kind,
            storage_path=body.photo_path,
            uploaded_by_uid=uid,
            weight_kg=body.weight_kg,
        )
    )
    target = await _target(db, job, kind)
    meters = round(haversine_km(body.lat, body.lon, target[0], target[1]) * 1000)
    db.add(
        JobLocation(
            job_id=job.id,
            transporter_id=job.transporter_id,
            kind=kind,
            lat=body.lat,
            lon=body.lon,
            accuracy_m=body.accuracy_m,
            distance_from_target_m=meters,
            recorded_at=stamp,
        )
    )
    await db.flush()
    actor = SimpleNamespace(uid=uid, role="transporter")
    event = "job.picked_up" if kind == "pickup" else "job.delivered"
    await emit(db, event, job_id=job.id, actor=actor, weight_kg=body.weight_kg)
    if meters > FAR_METERS:
        far = "job.pickup_far" if kind == "pickup" else "job.delivery_far"
        await emit(db, far, job_id=job.id, actor=actor, km=round(meters / 1000))


async def _target(db: AsyncSession, job: Job, kind: str) -> tuple[float, float]:
    """Where this step should happen: the farm for a pickup, the factory for a delivery."""
    if kind == "pickup":
        lot = await db.get(Lot, job.lot_id)
        return lot.lat, lot.lon
    factory = await db.get(Factory, job.factory_id)
    return factory.lat, factory.lon
