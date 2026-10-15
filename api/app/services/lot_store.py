"""Lot persistence shared by the agent route now and the admin routes later (A1/A2)."""
import uuid

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db_models.tables import Job, Lot, ResidueType, Village
from app.models.lot import LotEditIn, LotReadback
from app.services.lots import (
    PICKUP_PARTS,
    PKT,
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


LOCKED = "This lot is already funded and can no longer be changed"


def _current_pickup(lot: Lot) -> tuple[str, str]:
    """The lot's pickup day (YYYY-MM-DD) and part of day, read back from its stored window."""
    start = lot.pickup_from.astimezone(PKT)
    part = next((p for p, (t, _) in PICKUP_PARTS.items() if t == start.time()), "morning")
    return start.date().isoformat(), part


async def edit_lot_record(db: AsyncSession, lot: Lot, body: LotEditIn) -> None:
    """Apply a partial change to an unfunded lot. Raises LotError (422) or HTTPException (409).

    The caller re-ranks (`assignment_store.reassign_lot`) and commits, inside a savepoint.
    """
    job = (
        await db.execute(select(Job).where(Job.lot_id == lot.id).with_for_update())
    ).scalar_one_or_none()
    if job is not None and job.state != "created":
        raise HTTPException(409, LOCKED)
    if body.quantity_tonnes is not None:
        lot.quantity_tonnes = validate_quantity(body.quantity_tonnes)
    if body.pickup_date is not None or body.pickup_part is not None:
        day, part = _current_pickup(lot)
        start, end = pickup_window(body.pickup_date or day, body.pickup_part or part)
        lot.pickup_from, lot.pickup_to = start, end
    if body.village is not None or body.district is not None:
        canon = canonical_district(body.district or lot.district or "")
        villages = [
            VillageRow(v.id, v.name, v.lat, v.lon)
            for v in (await db.execute(select(Village).where(Village.district == canon))).scalars()
        ]
        place = match_place(body.village or lot.village_name or "", canon, villages)
        lot.village_id, lot.village_name = place.village_id, place.village
        lot.district, lot.place_match = place.district, place.match
        lot.lat, lot.lon = place.lat, place.lon
    await db.flush()
