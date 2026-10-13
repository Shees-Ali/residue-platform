"""The ONLY routes the voice service may call: exactly four tools.

Do not add more without a decision-log entry in memory/decisions.md.
"""
from fastapi import APIRouter, Depends

from app.auth.google_oidc import voice_service_caller
from app.auth.idempotency import require_idempotency_key
from app.models.agent import CreateLotIn, EscalateIn, GetQuoteIn, RecordConfirmationIn
from app.routers._stub import todo

router = APIRouter(
    prefix="/api/agent", tags=["agent"], dependencies=[Depends(voice_service_caller)]
)


async def farmer_id_for_call(call_id: str) -> str:
    """Resolve the farmer from the stored call record. Never from anything the model says."""
    # TODO(F1)
    raise NotImplementedError


@router.post("/lots")
async def create_lot(body: CreateLotIn, key: str = Depends(require_idempotency_key)):
    # TODO(F1)
    todo("F1")


@router.post("/quote")
async def get_quote(body: GetQuoteIn):
    # TODO(F2)
    todo("F2")


@router.post("/escalations")
async def escalate(body: EscalateIn, key: str = Depends(require_idempotency_key)):
    # TODO(F3)
    todo("F3")


@router.post("/confirmations")
async def record_confirmation(
    body: RecordConfirmationIn, key: str = Depends(require_idempotency_key)
):
    # TODO(F4)
    todo("F4")
