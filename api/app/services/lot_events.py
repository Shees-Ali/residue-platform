"""The events of a lot being reported: received, then matched to a factory or left unmatched."""
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.db_models.tables import Job
from app.services.notify import emit


async def announce_new_lot(
    db: AsyncSession, lot_id: uuid.UUID | str, job: Job | None, actor: Any = None
) -> None:
    await emit(db, "lot.created", lot_id=lot_id, actor=actor)
    # the matching is the platform's answer, not the reporter's own act: they hear it too
    if job is not None:
        await emit(db, "lot.matched", job_id=job.id, actor=actor, include_actor=True)
    else:
        await emit(db, "lot.unmatched", lot_id=lot_id, actor=actor, include_actor=True)
