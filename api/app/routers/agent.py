"""The ONLY routes the voice service may call: exactly four tools.

Do not add more without a decision-log entry in memory/decisions.md.
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.google_oidc import voice_service_caller
from app.auth.idempotency import require_idempotency_key
from app.db_models.tables import Call
from app.deps import DbSession, Events
from app.models.agent import CreateLotIn, EscalateIn, GetQuoteIn, RecordConfirmationIn
from app.models.lot import LotReadback
from app.routers._stub import todo
from app.services.idempotency import request_hash, run_idempotent
from app.services.lot_store import create_lot_record

router = APIRouter(
    prefix="/api/agent", tags=["agent"], dependencies=[Depends(voice_service_caller)]
)


async def farmer_id_for_call(db: AsyncSession, call_id: str) -> uuid.UUID:
    """Resolve the farmer from the stored call record. Never from anything the model says."""
    try:
        call_uuid = uuid.UUID(call_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Unknown call") from None
    farmer_id = (await db.execute(select(Call.farmer_id).where(Call.id == call_uuid))).first()
    if farmer_id is None:
        raise HTTPException(status_code=404, detail="Unknown call")
    if farmer_id[0] is None:
        # TODO(F1): the call-start webhook links the caller's phone to a farmer record.
        raise HTTPException(status_code=409, detail="Call is not linked to a farmer")
    return farmer_id[0]


@router.post("/lots", response_model=LotReadback, status_code=201)
async def create_lot(
    db: DbSession,
    events: Events,
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
        return 201, readback.model_dump(mode="json")

    _, payload, replayed = await run_idempotent(
        db, key, "POST /api/agent/lots", request_hash(body.model_dump()), work
    )
    await db.commit()
    if not replayed:
        await events.publish("lot.created")  # TODO(A2): dashboards refetch on this
    return payload


@router.post("/quote")
async def get_quote(db: DbSession, body: GetQuoteIn):
    # TODO(F2)
    todo("F2")


@router.post("/escalations")
async def escalate(
    db: DbSession,
    events: Events,
    body: EscalateIn,
    key: str = Depends(require_idempotency_key),
):
    # TODO(F3)
    todo("F3")


@router.post("/confirmations")
async def record_confirmation(
    db: DbSession,
    events: Events,
    body: RecordConfirmationIn,
    key: str = Depends(require_idempotency_key),
):
    # TODO(F4)
    todo("F4")
