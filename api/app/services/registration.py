"""Self-signup and admin approval. Roles come from this table, never from the client's token."""
from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.bootstrap import is_bootstrap_admin
from app.auth.firebase import Claims
from app.config import phone_verification_required
from app.db_models.tables import (
    Factory,
    FactoryResidue,
    Farmer,
    ResidueType,
    Transporter,
    User,
    Village,
)
from app.models.me import MeOut, RegisterIn, UserOut
from app.services.dispatch import TIER_MAX_TONNES
from app.services.lots import LotError, PlaceMatch, VillageRow, canonical_district, match_place
from app.validation import PHONE_HELP, FieldErrors

NEEDS_APPROVAL = ("transporter", "factory")


async def _place(db: AsyncSession, village: str | None, district: str | None) -> PlaceMatch:
    try:
        canon = canonical_district(district or "")
    except LotError as e:
        err = FieldErrors([("district", e.message)])
        err.valid = e.valid
        raise err from None
    villages = [
        VillageRow(v.id, v.name, v.lat, v.lon)
        for v in (await db.execute(select(Village).where(Village.district == canon))).scalars()
    ]
    return match_place(village, canon, villages)


async def me_out(db: AsyncSession, user: User) -> MeOut:
    linked = None
    if user.role == "farmer":
        linked = (
            await db.execute(select(Farmer.id).where(Farmer.user_uid == user.uid))
        ).first() is not None
        linked = linked or not phone_verification_required()  # the record is made on first use
    return MeOut(
        uid=user.uid,
        email=user.email,
        role=user.role,
        status=user.status,
        display_name=user.display_name,
        phone=user.phone,
        farmer_linked=linked,
    )


async def register(db: AsyncSession, claims: Claims, body: RegisterIn) -> User:
    """Create the users row and the role's profile row. The caller commits."""
    if await db.get(User, claims.uid) is not None:
        raise HTTPException(409, "Already registered")
    email = claims.email.lower() if claims.email else None
    if email and (await db.execute(select(User.uid).where(User.email == email))).first():
        raise FieldErrors(
            [("email", "That email is already registered")], status=409, code="email_taken"
        )

    admin = is_bootstrap_admin(claims)
    role = "admin" if admin else body.role
    if not admin:
        _require_fields(body)
    status = "pending" if role in NEEDS_APPROVAL else "active"
    phone = body.phone if role == "transporter" else claims.phone
    if role == "farmer" and not phone_verification_required():
        phone = phone or body.phone  # optional and unverified until SMS is switched on
    user = User(
        uid=claims.uid,
        role=role,
        status=status,
        email=email,
        display_name=body.display_name.strip(),
        phone=phone,
    )
    db.add(user)
    await db.flush()  # the profile rows below reference users.uid
    if admin:
        return user
    if role == "farmer":
        await _link_farmer(db, user)
    elif role == "transporter":
        await _create_transporter(db, user, body)
    elif role == "factory":
        await _create_factory(db, user, body)
    return user


def _require_fields(body: RegisterIn) -> None:
    """Which optional fields each role needs. Reports every gap at once, by field."""
    missing: list[tuple[str, str]] = []
    if body.role in ("transporter", "factory"):
        if not body.village:
            missing.append(("village", "Village or area is required"))
        if not body.district:
            missing.append(("district", "District is required"))
    if body.role == "transporter" and not body.phone:
        missing.append(("phone", f"Phone is required for transporters. {PHONE_HELP}"))
    if body.role == "factory" and body.factory is None:
        missing.append(("factory.name", "Factory name is required"))
        missing.append(("factory.price_per_tonne", "Price per tonne is required"))
        missing.append(("factory.residues", "Choose at least one residue you buy"))
    if missing:
        raise FieldErrors(missing, code="required")


async def ensure_farmer(db: AsyncSession, user: User) -> Farmer | None:
    """The farmer record of this login. Made on the spot when SMS verification is not required
    (a farmer may have no phone); otherwise None until the phone is verified."""
    farmer = (
        await db.execute(select(Farmer).where(Farmer.user_uid == user.uid))
    ).scalar_one_or_none()
    if farmer is None and not phone_verification_required():
        await _link_farmer(db, user)
        farmer = (
            await db.execute(select(Farmer).where(Farmer.user_uid == user.uid))
        ).scalar_one_or_none()
    return farmer


async def _link_farmer(db: AsyncSession, user: User) -> None:
    """Attach the farmer record for the phone on the user. With no phone: a record only when
    verification is not required."""
    if not user.phone:
        if not phone_verification_required():
            db.add(Farmer(phone=None, name=user.display_name, user_uid=user.uid))
            await db.flush()
        return
    farmer = (
        await db.execute(select(Farmer).where(Farmer.phone == user.phone))
    ).scalar_one_or_none()
    if farmer is None:
        db.add(Farmer(phone=user.phone, name=user.display_name, user_uid=user.uid))
    elif farmer.user_uid == user.uid:
        return  # already linked to this login: linking again changes nothing
    elif farmer.user_uid is not None:
        raise FieldErrors(
            [("phone", "That phone number is already linked to another account")],
            status=409, code="phone_taken",
        )
    else:
        farmer.user_uid = user.uid
        farmer.name = farmer.name or user.display_name
    await db.flush()


async def link_farmer_phone(db: AsyncSession, user: User, claims: Claims) -> None:
    """Attach the farmer record for the SMS-verified phone on the token, for a farmer who signed up
    without one. The number comes from the token, never from the request body."""
    if not claims.phone:
        raise FieldErrors([("phone", "Verify your phone number to continue")], code="not_verified")
    if user.phone and user.phone != claims.phone:
        user.phone = claims.phone
    user.phone = claims.phone
    await _link_farmer(db, user)


async def _create_transporter(db: AsyncSession, user: User, body: RegisterIn) -> None:
    place = await _place(db, body.village, body.district)
    db.add(
        Transporter(
            user_uid=user.uid,
            phone=body.phone,
            tier=1,
            max_tonnes=TIER_MAX_TONNES[1],
            lat=place.lat,
            lon=place.lon,
        )
    )
    await db.flush()


async def _create_factory(db: AsyncSession, user: User, body: RegisterIn) -> None:
    profile = body.factory
    assert profile is not None  # _require_fields checked
    known = set((await db.execute(select(ResidueType.code))).scalars())
    unknown = sorted(set(profile.residues) - known)
    if unknown:
        raise FieldErrors(
            [("factory.residues", f"Unknown residue types: {', '.join(unknown)}")],
            code="unknown_residue",
        )
    place = await _place(db, body.village, body.district)
    factory = Factory(
        user_uid=user.uid,
        name=profile.name,
        lat=place.lat,
        lon=place.lon,
        price_per_tonne=profile.price_per_tonne,
    )
    db.add(factory)
    await db.flush()
    db.add_all(FactoryResidue(factory_id=factory.id, residue_code=c) for c in set(profile.residues))
    await db.flush()


# --- admin: approve, reject, suspend, reactivate ---------------------------------------------


async def _transporter(db: AsyncSession, uid: str) -> Transporter | None:
    return (
        await db.execute(select(Transporter).where(Transporter.user_uid == uid))
    ).scalar_one_or_none()


async def change_status(
    db: AsyncSession, admin_uid: str, uid: str, action: str, tier: int = 1
) -> User:
    """approve (pending->active), reject (pending->suspended), suspend (active->suspended),
    reactivate (suspended->active). Transporters are dispatchable only while approved_at is set."""
    user = await db.get(User, uid)
    if user is None:
        raise HTTPException(404, "Unknown user")
    if action == "suspend" and uid == admin_uid:
        raise HTTPException(409, "You cannot suspend yourself")
    allowed = {
        "approve": ("pending", "active"),
        "reject": ("pending", "suspended"),
        "suspend": ("active", "suspended"),
        "reactivate": ("suspended", "active"),
    }
    required, new_status = allowed[action]
    if user.status != required:
        raise HTTPException(409, f"Cannot {action} a user who is {user.status}")
    user.status = new_status
    if user.role == "transporter":
        transporter = await _transporter(db, uid)
        if transporter is not None:
            if new_status == "active":
                if action == "approve":
                    transporter.tier = tier
                    transporter.max_tonnes = TIER_MAX_TONNES[tier]
                transporter.approved_at = transporter.approved_at or datetime.now(UTC)
            else:
                transporter.approved_at = None
    await db.flush()
    return user


async def user_out(db: AsyncSession, user: User) -> UserOut:
    details: dict = {}
    if user.role == "transporter":
        t = await _transporter(db, user.uid)
        if t is not None:
            details = {"phone": t.phone, "tier": t.tier, "max_tonnes": float(t.max_tonnes)}
    elif user.role == "factory":
        f = (
            await db.execute(select(Factory).where(Factory.user_uid == user.uid))
        ).scalar_one_or_none()
        if f is not None:
            residues = (
                await db.execute(
                    select(FactoryResidue.residue_code).where(FactoryResidue.factory_id == f.id)
                )
            ).scalars().all()
            details = {
                "name": f.name,
                "price_per_tonne": f.price_per_tonne,
                "residues": sorted(residues),
            }
    return UserOut(
        uid=user.uid,
        email=user.email,
        role=user.role,
        status=user.status,
        display_name=user.display_name,
        phone=user.phone,
        created_at=user.created_at,
        details=details,
    )
