"""Edit my details, and the admin's edit of anyone. One service for both so the rules cannot drift.

Edits apply at once. They are safe because a job's price is locked when the lot is assigned and
offers read the transporter's base live: an edit only changes what happens to later lots and offers.
"""
import logging
from datetime import UTC, datetime
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db_models.tables import Factory, FactoryResidue, Farmer, Transporter, User
from app.models.profile import (
    FactoryProfileOut,
    ProfileEditIn,
    ProfileOut,
    TransporterProfileOut,
)
from app.services.dispatch import TIER_MAX_TONNES
from app.services.registration import _place, check_residues
from app.validation import FieldErrors

log = logging.getLogger("profile")

PLACE_ROLES = ("transporter", "factory")


async def _factory(db: AsyncSession, uid: str) -> Factory | None:
    return (await db.execute(select(Factory).where(Factory.user_uid == uid))).scalar_one_or_none()


async def _transporter(db: AsyncSession, uid: str) -> Transporter | None:
    return (
        await db.execute(select(Transporter).where(Transporter.user_uid == uid))
    ).scalar_one_or_none()


async def profile_out(db: AsyncSession, user: User) -> ProfileOut:
    out = ProfileOut(
        uid=user.uid, email=user.email, role=user.role, status=user.status,
        display_name=user.display_name, phone=user.phone,
    )
    if user.role == "factory" and (f := await _factory(db, user.uid)):
        residues = (
            await db.execute(
                select(FactoryResidue.residue_code).where(FactoryResidue.factory_id == f.id)
            )
        ).scalars().all()
        out.district, out.village = f.district, f.village
        out.factory = FactoryProfileOut(
            name=f.name, price_per_tonne=f.price_per_tonne, residues=sorted(residues)
        )
    elif user.role == "transporter" and (t := await _transporter(db, user.uid)):
        out.district, out.village = t.district, t.village
        out.transporter = TransporterProfileOut(
            tier=t.tier, max_tonnes=float(t.max_tonnes), approved=t.approved_at is not None
        )
    return out


def _refuse_foreign_fields(user: User, body: ProfileEditIn, admin: bool) -> None:
    errors: list[tuple[str, str]] = []
    if body.factory is not None and user.role != "factory":
        errors.append(("factory", "Only factories have factory details"))
    if body.transporter is not None:
        if not admin:
            errors.append(("transporter.tier", "Only an admin can change tier"))
        elif user.role != "transporter":
            errors.append(("transporter", "Only transporters have a tier and max load"))
    if user.role not in PLACE_ROLES and (body.district or body.village):
        errors.append(("district", "Only transporters and factories have a base place"))
    if errors:
        raise FieldErrors(errors, code="not_editable")


async def _phone_free(db: AsyncSession, user: User, phone: str) -> None:
    """A farmer's phone ties them to their lots, so it cannot be one another farmer already has."""
    other = (
        await db.execute(
            select(Farmer.user_uid, Farmer.id).where(Farmer.phone == phone)
        )
    ).first()
    mine = (await db.execute(select(Farmer.id).where(Farmer.user_uid == user.uid))).scalar()
    if other is not None and other.id != mine:
        raise FieldErrors(
            [("phone", "That phone number is already linked to another account")],
            status=409, code="phone_taken",
        )


async def update_profile(
    db: AsyncSession, target: User, body: ProfileEditIn, *, admin: bool
) -> User:
    """Apply a partial edit. The caller commits, inside a savepoint so a refusal changes nothing."""
    if target.status == "suspended" and not admin:
        raise HTTPException(403, "Your account is suspended. Contact an admin.")
    if not body.model_fields_set or all(getattr(body, f) is None for f in body.model_fields_set):
        raise FieldErrors([("body", "Change at least one field")], code="empty")
    _refuse_foreign_fields(target, body, admin)

    now = datetime.now(UTC)
    changed: list[str] = []
    factory = await _factory(db, target.uid) if target.role == "factory" else None
    transporter = await _transporter(db, target.uid) if target.role == "transporter" else None

    if body.display_name is not None:
        target.display_name = body.display_name
        changed.append("display_name")

    if body.phone is not None:
        if target.role == "farmer":
            await _phone_free(db, target, body.phone)
            farmer = (
                await db.execute(select(Farmer).where(Farmer.user_uid == target.uid))
            ).scalar_one_or_none()
            if farmer is not None:
                farmer.phone = body.phone
        target.phone = body.phone
        if transporter is not None:
            transporter.phone = body.phone
        changed.append("phone")

    holder = factory or transporter
    if holder is not None and (body.district is not None or body.village is not None):
        district = body.district or holder.district
        village = body.village or holder.village
        if not district:
            raise FieldErrors([("district", "District is required")], code="required")
        if not village:
            raise FieldErrors([("village", "Village or area is required")], code="required")
        place = await _place(db, village, district)
        holder.district, holder.village = place.district, place.village
        holder.lat, holder.lon = place.lat, place.lon
        holder.updated_at = now
        changed += [f for f in ("district", "village") if getattr(body, f) is not None]

    if factory is not None and body.factory is not None:
        f = body.factory
        if f.name is not None:
            factory.name = f.name
            changed.append("factory.name")
        if f.price_per_tonne is not None:
            factory.price_per_tonne = f.price_per_tonne
            changed.append("factory.price_per_tonne")
        if f.residues is not None:
            await check_residues(db, f.residues)
            await db.execute(delete(FactoryResidue).where(FactoryResidue.factory_id == factory.id))
            db.add_all(
                FactoryResidue(factory_id=factory.id, residue_code=c) for c in set(f.residues)
            )
            changed.append("factory.residues")
        factory.updated_at = now

    if transporter is not None and body.transporter is not None:
        t = body.transporter
        if t.tier is not None:
            transporter.tier = t.tier
            transporter.max_tonnes = Decimal(TIER_MAX_TONNES[t.tier])  # the tier's default load
            changed.append("transporter.tier")
        if t.max_tonnes is not None:
            transporter.max_tonnes = Decimal(str(t.max_tonnes))
            changed.append("transporter.max_tonnes")
        transporter.updated_at = now

    await db.flush()
    log.info("profile edited uid=%s by_admin=%s fields=%s", target.uid, admin, ",".join(changed))
    return target
