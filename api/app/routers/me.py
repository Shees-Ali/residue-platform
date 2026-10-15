from fastapi import APIRouter, Depends, HTTPException

from app.auth.bootstrap import ensure_bootstrap_admin
from app.auth.firebase import DEV_ADMIN_UID, AuthUser, Claims, current_user, verified_claims
from app.config import auth_bypass_active
from app.db_models.tables import User
from app.deps import DbSession
from app.models.me import MeOut, RegisterIn
from app.models.profile import ProfileEditIn, ProfileOut
from app.services.profile import profile_out, update_profile
from app.services.registration import link_farmer_phone, me_out, register

router = APIRouter(prefix="/api/me", tags=["me"])


@router.get("", response_model=MeOut)
async def get_me(db: DbSession, claims: Claims = Depends(verified_claims)):
    """Who the signed-in person is. 404 `not_registered` means: show the signup form."""
    user = await db.get(User, claims.uid)
    granted = await ensure_bootstrap_admin(db, claims)  # a listed, verified email is admin now
    if granted is not None:
        user = granted
        await db.commit()
    if user is None:
        if auth_bypass_active() and claims.uid == DEV_ADMIN_UID:
            return MeOut(
                uid=claims.uid, email=None, role="admin", status="active", display_name="Dev admin",
                phone=None,
            )
        raise HTTPException(
            404, {"code": "not_registered", "message": "Sign up to choose a role"}
        )
    return await me_out(db, user)


@router.post("/register", response_model=MeOut, status_code=201)
async def register_me(db: DbSession, body: RegisterIn, claims: Claims = Depends(verified_claims)):
    """First sign-in: pick a role. Farmers and buyers are active at once; transporters and
    factories wait for an admin. Admin is never self-selected."""
    async with db.begin_nested():  # a rejected signup leaves no half-made account behind
        user = await register(db, claims, body)
    out = await me_out(db, user)
    await db.commit()
    return out


@router.post("/link-phone", response_model=MeOut)
async def link_phone(
    db: DbSession, claims: Claims = Depends(verified_claims), who: AuthUser = Depends(current_user)
):
    """A farmer who has no linked record verifies their phone (SMS) and calls this."""
    if who.role != "farmer":
        raise HTTPException(403, "Only farmers have a phone to link")
    user = await db.get(User, who.uid)
    async with db.begin_nested():
        await link_farmer_phone(db, user, claims)
    out = await me_out(db, user)
    await db.commit()
    return out


async def _own_row(db: DbSession, claims: Claims) -> User:
    """The caller's own row, whatever its status: a pending account may fix its details too."""
    user = await db.get(User, claims.uid)
    if user is None:
        raise HTTPException(
            403, {"code": "not_registered", "message": "This account has no role; sign up first"}
        )
    return user


@router.get("/profile", response_model=ProfileOut)
async def get_profile(db: DbSession, claims: Claims = Depends(verified_claims)):
    """My editable details (name, phone, base place, factory price and residues)."""
    return await profile_out(db, await _own_row(db, claims))


@router.patch("/profile", response_model=ProfileOut)
async def patch_profile(
    db: DbSession, body: ProfileEditIn, claims: Claims = Depends(verified_claims)
):
    """Change my own details. Only the fields sent change; a refused edit changes nothing."""
    user = await _own_row(db, claims)
    async with db.begin_nested():
        await update_profile(db, user, body, admin=False)
    out = await profile_out(db, user)
    await db.commit()
    return out
