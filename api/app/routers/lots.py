from fastapi import APIRouter, Depends

from app.auth.firebase import current_user
from app.routers._stub import todo

router = APIRouter(prefix="/api/lots", tags=["lots"], dependencies=[Depends(current_user)])


@router.get("")
async def get_lots_root():
    # TODO(F1)
    todo("F1")


@router.post("")
async def post_lots_root():
    # TODO(F1)
    todo("F1")


@router.get("/{lot_id}/ranking")
async def get_lots_lot_id_ranking(lot_id: str):
    # TODO(A1)
    todo("A1")
