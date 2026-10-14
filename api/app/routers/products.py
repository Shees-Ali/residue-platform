from fastapi import APIRouter, Depends

from app.auth.firebase import current_user
from app.deps import DbSession, Events
from app.routers._stub import todo

router = APIRouter(prefix="/api/products", tags=["products"], dependencies=[Depends(current_user)])


@router.get("")
async def get_products_root(db: DbSession):
    # TODO(B1)
    todo("B1")


@router.post("")
async def post_products_root(db: DbSession, events: Events):
    # TODO(FA3)
    todo("FA3")
