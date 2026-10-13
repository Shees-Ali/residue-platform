from fastapi import APIRouter, Depends

from app.auth.firebase import current_user
from app.routers._stub import todo

router = APIRouter(prefix="/api/offers", tags=["offers"], dependencies=[Depends(current_user)])


@router.get("")
async def get_offers_root():
    # TODO(T1)
    todo("T1")


@router.post("/{offer_id}/accept")
async def post_offers_offer_id_accept(offer_id: str):
    # TODO(T1)
    todo("T1")
