from fastapi import APIRouter, Depends

from app.auth.firebase import current_user
from app.routers._stub import todo

router = APIRouter(prefix="/api/orders", tags=["orders"], dependencies=[Depends(current_user)])


@router.post("")
async def post_orders_root():
    # TODO(B1)
    todo("B1")


@router.get("/{order_id}/split")
async def get_orders_order_id_split(order_id: str):
    # TODO(FA3)
    todo("FA3")
