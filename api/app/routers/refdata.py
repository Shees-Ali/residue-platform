"""Lookup lists the forms need, so the web does not hardcode them."""
from fastapi import APIRouter, Depends
from sqlalchemy import select

from app.auth.firebase import AuthUser, current_user
from app.db_models.tables import ResidueType, Village
from app.deps import DbSession
from app.models.refdata import ResidueTypeOut, VillageOut
from app.services.lot_errors import as_field_errors
from app.services.lots import LotError, canonical_district
from app.services.places import DISTRICTS

router = APIRouter(prefix="/api", tags=["reference"])


@router.get("/residue-types", response_model=list[ResidueTypeOut])
async def get_residue_types(db: DbSession, user: AuthUser = Depends(current_user)):
    rows = (await db.execute(select(ResidueType).order_by(ResidueType.label))).scalars().all()
    return [ResidueTypeOut(code=r.code, label=r.label) for r in rows]


@router.get("/districts", response_model=list[str])
async def get_districts(user: AuthUser = Depends(current_user)):
    return sorted(DISTRICTS)


@router.get("/villages", response_model=list[VillageOut])
async def get_villages(db: DbSession, district: str, user: AuthUser = Depends(current_user)):
    """Known villages in a district, for suggestions. Any other village name is still accepted."""
    try:
        canon = canonical_district(district)
    except LotError as e:
        raise as_field_errors(e) from None
    rows = (
        await db.execute(select(Village).where(Village.district == canon).order_by(Village.name))
    ).scalars().all()
    return [VillageOut(name=v.name, district=v.district) for v in rows]
