"""F4: the farmer's yes or no on weight and payment, after the factory has confirmed."""
import uuid

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db_models.tables import Call, Escalation, Farmer, Job, Lot, Verification
from app.services.settlement import dispute, settle_verified
from app.validation import FieldErrors


async def verification_call_for(db: AsyncSession, job: Job) -> Call:
    """Admin demo button: open a verification call row for the job's farmer."""
    if job.state != "confirmed":
        raise HTTPException(409, "A verification call can start once the factory has confirmed")
    lot = await db.get(Lot, job.lot_id)
    call = Call(farmer_id=lot.farmer_id, kind="verification", status="in_progress")
    db.add(call)
    await db.flush()
    return call


async def record_web_answer(
    db: AsyncSession, farmer_uid: str, job_id: str, confirmed: bool, note: str
) -> dict:
    """The same yes or no as the phone call, given by the farmer signed in on the web.

    Yes settles and releases the payout; no freezes it and puts an alert in the admin queue. The
    job must be the farmer's own and the factory must have confirmed the weight first.
    """
    if not confirmed and len(note.strip()) < 3:
        raise FieldErrors(
            [("note", "Tell us what is wrong (at least 3 characters)")], code="note_required"
        )
    try:
        job_key = uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(404, "Unknown job") from None
    job = (
        await db.execute(select(Job).where(Job.id == job_key).with_for_update())
    ).scalar_one_or_none()
    owner = None
    if job is not None:
        owner = (
            await db.execute(
                select(Farmer.user_uid).join(Lot, Lot.farmer_id == Farmer.id).where(
                    Lot.id == job.lot_id
                )
            )
        ).scalar_one_or_none()
    if job is None or owner != farmer_uid:
        raise HTTPException(404, "Unknown job")
    if job.state != "confirmed":
        raise HTTPException(409, f"The job is '{job.state}', not waiting for your confirmation")

    db.add(Verification(job_id=job.id, call_id=None, confirmed=confirmed, note=note.strip()))
    if confirmed:
        parts = await settle_verified(db, job)
        return {"job_id": str(job.id), "state": "settled", "farmer_amount": parts["farmer"]}
    await dispute(db, job)
    db.add(
        Escalation(
            job_id=job.id,
            summary=(
                f"Farmer disputed the weight or payment for job {job.id}. {note.strip()}"
            ).strip(),
        )
    )
    await db.flush()
    return {"job_id": str(job.id), "state": "disputed", "farmer_amount": None}


async def record_answer(
    db: AsyncSession, call_id: str, job_id: str, confirmed: bool, note: str
) -> dict:
    """Yes settles and releases the payout; no freezes it and puts an alert in the admin queue.

    The farmer is whoever the call belongs to, and the job must be theirs: the model can't pick.
    """
    try:
        call_key, job_key = uuid.UUID(call_id), uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(404, "Unknown call or job") from None
    call = await db.get(Call, call_key)
    if call is None or call.kind != "verification" or call.farmer_id is None:
        raise HTTPException(404, "Unknown verification call")
    job = (
        await db.execute(select(Job).where(Job.id == job_key).with_for_update())
    ).scalar_one_or_none()
    lot = await db.get(Lot, job.lot_id) if job else None
    if job is None or lot.farmer_id != call.farmer_id:
        raise HTTPException(404, "Unknown job")
    if job.state != "confirmed":
        raise HTTPException(409, f"The job is '{job.state}', not waiting for verification")

    db.add(Verification(job_id=job.id, call_id=call.id, confirmed=confirmed, note=note))
    if confirmed:
        parts = await settle_verified(db, job)
        return {
            "job_id": str(job.id), "state": "settled",
            "farmer_amount": parts["farmer"],
            "farmer_amount_rupees": round(parts["farmer"] / 100, 2),
        }
    await dispute(db, job)
    db.add(
        Escalation(
            call_id=call.id,
            summary=f"Farmer disputed the weight or payment for job {job.id}. {note}".strip(),
        )
    )
    await db.flush()
    return {"job_id": str(job.id), "state": "disputed"}

