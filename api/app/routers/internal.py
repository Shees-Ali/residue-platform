"""Service-to-service routes for the voice transport layer.

NOT model tools: the agent never calls these (the agent-tool rule covers /api/agent/* only).
They create the call record that links a caller's phone number to a farmer, which is where
every agent tool later gets its identity.
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert

from app.auth.google_oidc import voice_service_caller
from app.db_models.tables import Call, Farmer
from app.deps import DbSession
from app.models.call import CallEndIn, CallEndOut, CallStartIn, CallStartOut

router = APIRouter(
    prefix="/api/internal", tags=["internal"], dependencies=[Depends(voice_service_caller)]
)


@router.post("/calls", response_model=CallStartOut)
async def start_call(db: DbSession, body: CallStartIn):
    """Link the caller's number to a farmer (creating one if new) and open a call record.

    A verification call opened by the API (sid `verify-<id>`) is reused rather than duplicated.
    Each call record connects once (in_progress -> connected): a second start for the same sid
    is refused (409), as is a sid that belongs to another farmer or kind, so a replayed or
    forged stream cannot attach to anyone's call record.
    """
    await db.execute(
        insert(Farmer).values(phone=body.caller_phone).on_conflict_do_nothing(
            index_elements=["phone"]
        )
    )
    farmer = (
        await db.execute(select(Farmer).where(Farmer.phone == body.caller_phone))
    ).scalar_one()
    await db.execute(
        insert(Call)
        .values(twilio_call_sid=body.twilio_call_sid, farmer_id=farmer.id, kind=body.kind)
        .on_conflict_do_nothing(index_elements=["twilio_call_sid"])
    )
    # Locked until the commit, so two concurrent starts cannot both connect the same call.
    call = (
        await db.execute(
            select(Call).where(Call.twilio_call_sid == body.twilio_call_sid).with_for_update()
        )
    ).scalar_one()
    if call.kind != body.kind or call.farmer_id != farmer.id:
        # The reference belongs to someone else's call (or another kind): never hand it over.
        raise HTTPException(status_code=409, detail="Call reference does not match this caller")
    if call.status != "in_progress":
        # Every call record connects once: a replayed stream (e.g. a URL copied from logs, on
        # another instance) cannot attach to a live or ended call, or answer a verification.
        raise HTTPException(status_code=409, detail="Call already connected")
    call.status = "connected"
    await db.commit()
    return CallStartOut(call_id=str(call.id), farmer_known=bool(farmer.name))


@router.post("/calls/{call_id}/end", response_model=CallEndOut)
async def end_call(db: DbSession, call_id: str, body: CallEndIn):
    try:
        call_uuid = uuid.UUID(call_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Unknown call") from None
    updated = (
        await db.execute(
            update(Call)
            .where(Call.id == call_uuid)
            .values(status=body.status, transcript=body.transcript, summary=body.summary)
            .returning(Call.id)
        )
    ).first()
    if updated is None:
        raise HTTPException(status_code=404, detail="Unknown call")
    await db.commit()
    return CallEndOut(call_id=call_id, status=body.status)
