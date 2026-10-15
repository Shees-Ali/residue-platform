"""Lot persistence shared by the agent route now and the admin routes later (A1/A2)."""
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db_models.tables import Lot, ResidueType, Village
from app.models.lot import LotReadback
from app.services.lots import (
    VillageRow,
    canonical_district,
    match_place,
    pickup_text,
    pickup_window,
    validate_quantity,
    validate_residue,
)


async def create_lot_record(
    db: AsyncSession,
    *,
    farmer_id: uuid.UUID,
    call_id: uuid.UUID | None,
    residue_type: str,
    quantity_tonnes: float,
    pickup_date: str,
    pickup_part: str,
    village: str,
    district: str,
) -> LotReadback:
    """Validate, resolve the place, insert an `open` lot. Raises LotError (caller returns 422)."""
    residues = {r.code: r.label for r in (await db.execute(select(ResidueType))).scalars()}
    code = validate_residue(residue_type, residues)
    quantity = validate_quantity(quantity_tonnes)
    start, end = pickup_window(pickup_date, pickup_part)
    canon = canonical_district(district)
    villages = [
        VillageRow(v.id, v.name, v.lat, v.lon)
        for v in (await db.execute(select(Village).where(Village.district == canon))).scalars()
    ]
    place = match_place(village, canon, villages)

    lot = Lot(
        farmer_id=farmer_id,
        call_id=call_id,
        residue_code=code,
        quantity_tonnes=quantity,
        pickup_from=start,
        pickup_to=end,
        village_id=place.village_id,
        village_name=place.village,
        district=place.district,
        place_match=place.match,
        lat=place.lat,
        lon=place.lon,
        status="open",
    )
    db.add(lot)
    await db.flush()
    return LotReadback(
        lot_id=str(lot.id),
        residue_type=code,
        residue_label=residues[code],
        quantity_tonnes=float(quantity),
        village=place.village,
        district=place.district,
        place_match=place.match,
        pickup_from=start,
        pickup_to=end,
        pickup_text=pickup_text(start, end),
    )
