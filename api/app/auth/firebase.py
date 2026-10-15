"""Dashboard auth: a Firebase ID token proves who you are; the `users` table says what you are."""
import logging
import os
from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException, Security
from fastapi.security import HTTPBearer
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from sqlalchemy import select
from starlette.concurrency import run_in_threadpool

from app.auth.bootstrap import ensure_bootstrap_admin
from app.config import auth_bypass_active, get_settings
from app.db_models.tables import User
from app.deps import DbSession

log = logging.getLogger(__name__)

DEV_ADMIN_UID = "dev-admin"


def clock_skew_seconds() -> int:
    """A fresh token is rejected if this machine clock runs behind Google. Allow some drift
    (AUTH_CLOCK_SKEW_SECONDS, default 60); tokens still expire an hour after issue."""
    return int(os.getenv("AUTH_CLOCK_SKEW_SECONDS", "60"))

# Only here so OpenAPI declares a bearer scheme (Swagger's Authorize button); the token itself is
# read from the Authorization header below.
bearer_scheme = HTTPBearer(auto_error=False)
_declare_bearer = Security(bearer_scheme)


@dataclass(frozen=True)
class AuthUser:
    uid: str
    role: str  # admin | transporter | factory | buyer | farmer


@dataclass(frozen=True)
class Claims:
    """What a valid Firebase token says about the caller, before any users row exists."""

    uid: str
    email: str | None = None
    email_verified: bool = False
    phone: str | None = None
    name: str | None = None


def _verify(token: str, project_id: str) -> dict:
    """Blocking: fetches Google's signing certs (cached). Run it in a thread."""
    return id_token.verify_firebase_token(
        token, google_requests.Request(), audience=project_id,
        clock_skew_in_seconds=clock_skew_seconds(),
    )


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(401, detail, headers={"WWW-Authenticate": "Bearer"})


async def verified_claims(
    authorization: str | None = Header(default=None),
    x_dev_uid: str | None = Header(default=None),
    x_dev_email: str | None = Header(default=None),
    x_dev_phone: str | None = Header(default=None),
    _scheme=_declare_bearer,
) -> Claims:
    """Verify the bearer token only.

    Local bypass: X-Dev-Uid picks an identity; X-Dev-Email / X-Dev-Phone stand in for verified
    token claims (used to try signup and the bootstrap admin without Firebase).
    """
    if auth_bypass_active():
        # (called directly, the header defaults are Header objects, not strings)
        email = x_dev_email if isinstance(x_dev_email, str) else None
        phone = x_dev_phone if isinstance(x_dev_phone, str) else None
        return Claims(
            x_dev_uid or DEV_ADMIN_UID, email=email, email_verified=bool(email), phone=phone
        )
    if not authorization or not authorization.lower().startswith("bearer "):
        raise _unauthorized("Missing bearer token")
    try:
        claims = await run_in_threadpool(
            _verify, authorization.split(" ", 1)[1].strip(), get_settings().firebase_project_id
        )
    except ValueError as e:
        log.warning("Firebase token rejected: %s", e)  # why, for the server log only
        if "too early" in str(e):  # a clock problem is fixable by the person, so say so
            raise _unauthorized(
                "Invalid token: this computer's clock is behind. Turn on automatic time in "
                "your system settings, then sign in again."
            ) from None
        raise _unauthorized("Invalid token") from None
    return Claims(
        uid=claims.get("sub") or claims.get("user_id") or "",
        email=claims.get("email"),
        email_verified=bool(claims.get("email_verified")),
        phone=claims.get("phone_number"),
        name=claims.get("name"),
    )


async def current_user(
    db: DbSession,
    authorization: str | None = Header(default=None),
    x_dev_uid: str | None = Header(default=None),
    _scheme=_declare_bearer,
    x_dev_email: str | None = Header(default=None),
) -> AuthUser:
    """Verify the caller and load their role. Only active accounts get through."""
    claims = await verified_claims(authorization, x_dev_uid, x_dev_email)
    if auth_bypass_active() and claims.uid == DEV_ADMIN_UID:
        return AuthUser(claims.uid, "admin")
    if claims.email:  # a listed, verified email is made admin here too, not only on /api/me
        granted = await ensure_bootstrap_admin(db, claims)
        if granted is not None:
            await db.commit()
            return AuthUser(claims.uid, "admin")
    row = (
        await db.execute(select(User.role, User.status).where(User.uid == claims.uid))
    ).first()
    if row is None:
        raise HTTPException(
            403, {"code": "not_registered", "message": "This account has no role; sign up first"}
        )
    role, status = row
    if status == "pending":
        raise HTTPException(
            403, {"code": "pending_approval", "message": "Waiting for an admin to approve you"}
        )
    if status != "active":
        raise HTTPException(403, {"code": "suspended", "message": "This account is suspended"})
    return AuthUser(claims.uid, role)


def require_role(*roles: str):
    async def checker(user: AuthUser = Depends(current_user)) -> AuthUser:
        if user.role not in roles:
            raise HTTPException(403, "Forbidden")
        return user

    return checker


# Reusable route dependencies: `user: AuthUser = as_factory`
as_admin = Depends(require_role("admin"))
as_factory = Depends(require_role("factory"))
as_transporter = Depends(require_role("transporter"))
as_buyer = Depends(require_role("buyer"))
as_farmer = Depends(require_role("farmer"))
