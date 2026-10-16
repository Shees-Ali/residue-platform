"""The ONLY routes the voice service may call: exactly four tools.

Do not add more without a decision-log entry in memory/decisions.md.
"""
import uuid

from fastapi import APIRouter, Depends

from app.auth.google_oidc import voice_service_caller
from app.auth.idempotency import require_idempotency_key
from app.deps import DbSession, Delivery
from app.models.agent import CreateLotIn, EscalateIn, GetQuoteIn, RecordConfirmationIn
from app.models.lot import LotReadback
from app.models.quote import QuoteOut
from app.services.assignment_store import assign_lot
from app.services.calls import farmer_id_for_call
from app.services.escalations import create_escalation
from app.services.idempotency import request_hash, run_idempotent
from app.services.inbox import commit_and_deliver
from app.services.lot_events import announce_new_lot
from app.services.lot_store import create_lot_record
from app.services.notify import emit
from app.services.quotes import quote_for
from app.services.verification import record_answer

router = APIRouter(
    prefix="/api/agent", tags=["agent"], dependencies=[Depends(voice_service_caller)]
)


@router.post("/lots", response_model=LotReadback, status_code=201)
async def create_lot(
    db: DbSession,
    inbox: Delivery,
    body: CreateLotIn,
    key: str = Depends(require_idempotency_key),
):
    """Save the caller's lot. The farmer comes from the call record; replays return the original."""
    farmer_id = await farmer_id_for_call(db, body.call_id)

    async def work() -> tuple[int, dict]:
        readback = await create_lot_record(
            db,
            farmer_id=farmer_id,
            call_id=uuid.UUID(body.call_id),
            residue_type=body.residue_type,
            quantity_tonnes=body.quantity_tonnes,
            pickup_date=body.pickup_date,
            pickup_part=body.pickup_part,
            village=body.village,
            district=body.district,
        )
        job = await assign_lot(db, uuid.UUID(readback.lot_id))  # A1: ranked in the same transaction
        await announce_new_lot(db, readback.lot_id, job)
        return 201, readback.model_dump(mode="json")

    _, payload, replayed = await run_idempotent(
        db, key, "POST /api/agent/lots", request_hash(body.model_dump()), work
    )
    await commit_and_deliver(db, inbox)
    return payload


@router.post("/quote", response_model=QuoteOut)
async def get_quote(db: DbSession, body: GetQuoteIn):
    """Price per tonne, the farmer's share and when they are paid, for one of their own lots."""
    farmer_id = await farmer_id_for_call(db, body.call_id)
    return await quote_for(db, farmer_id, body.lot_id)


@router.post("/escalations", status_code=201)
async def escalate(
    db: DbSession,
    inbox: Delivery,
    body: EscalateIn,
    key: str = Depends(require_idempotency_key),
):
    """The caller needs a person: save the summary and transcript to the admin queue."""
    await farmer_id_for_call(db, body.call_id)  # the call must exist and be linked

    async def work() -> tuple[int, dict]:
        row = await create_escalation(db, body.call_id, body.summary, body.transcript)
        await emit(db, "escalation.created")
        return 201, {"escalation_id": str(row.id), "status": "open"}

    _, payload, replayed = await run_idempotent(
        db, key, "POST /api/agent/escalations", request_hash(body.model_dump()), work
    )
    await commit_and_deliver(db, inbox)
    return payload


@router.post("/confirmations")
async def record_confirmation(
    db: DbSession,
    inbox: Delivery,
    body: RecordConfirmationIn,
    key: str = Depends(require_idempotency_key),
):
    """The farmer's yes or dispute on weight and payment. Yes settles; a dispute freezes."""

    async def work() -> tuple[int, dict]:
        return 200, await record_answer(db, body.call_id, body.job_id, body.confirmed, body.note)

    status, payload, replayed = await run_idempotent(
        db, key, "POST /api/agent/confirmations", request_hash(body.model_dump()), work
    )
    await commit_and_deliver(db, inbox)
    return payload
