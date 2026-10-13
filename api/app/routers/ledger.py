from fastapi import APIRouter, Depends

from app.auth.firebase import current_user
from app.routers._stub import todo

router = APIRouter(prefix="/api/ledger", tags=["ledger"], dependencies=[Depends(current_user)])


@router.get("")
async def get_ledger_root():
    # TODO(A3)
    todo("A3")


@router.get("/check")
async def get_ledger_check():
    # TODO(A3)
    todo("A3")


@router.post("/escrow")
async def post_ledger_escrow():
    # TODO(FA1)
    todo("FA1")
