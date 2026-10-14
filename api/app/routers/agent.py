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
from app.routers._stub import todo

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


@router.post("/lots")
async def create_lot(
    db: DbSession,
    events: Events,
    body: CreateLotIn,
    key: str = Depends(require_idempotency_key),
):
    # TODO(F1): farmer = await farmer_id_for_call(db, body.call_id); insert lot; commit; publish.
    todo("F1")


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
