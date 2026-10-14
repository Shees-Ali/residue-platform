"""T2: the transporter proves pickup and delivery with a photo and a weight."""
from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db_models.tables import Job, Photo
from app.services.job_flow import transition
from app.services.storage import photo_prefix

MAX_WEIGHT_KG = 100_000

# kind -> (state before, state after, timestamp column)
LEGS = {
    "pickup": ("accepted", "picked_up", "picked_up_at"),
    "delivery": ("picked_up", "delivered", "delivered_at"),
}


def check_photo_path(job_id: str, kind: str, path: str) -> None:
    if not path.startswith(photo_prefix(job_id, kind)):
        raise HTTPException(422, f"photo_path must be an upload for this job's {kind} photo")


def check_weight(weight_kg: int) -> None:
    if not 0 < weight_kg <= MAX_WEIGHT_KG:
        raise HTTPException(422, f"weight_kg must be between 1 and {MAX_WEIGHT_KG}")


async def record_leg(
    db: AsyncSession,
    job: Job,
    kind: str,
    uid: str,
    photo_path: str,
    weight_kg: int,
    now: datetime | None = None,
) -> None:
    """Move accepted -> picked_up or picked_up -> delivered, storing the photo and weight."""
    check_photo_path(str(job.id), kind, photo_path)
    check_weight(weight_kg)
    before, after, column = LEGS[kind]
    await transition(db, job.id, before, after, **{column: now or datetime.now(UTC)})
    db.add(
        Photo(
            job_id=job.id,
            kind=kind,
            storage_path=photo_path,
            uploaded_by_uid=uid,
            weight_kg=weight_kg,
        )
    )
    await db.flush()
