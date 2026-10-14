"""Dashboard auth: a Firebase ID token proves who you are; the `users` table says what you are."""
from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from sqlalchemy import select
from starlette.concurrency import run_in_threadpool

from app.config import auth_bypass_active, get_settings
from app.db_models.tables import User
from app.deps import DbSession

DEV_ADMIN_UID = "dev-admin"


@dataclass(frozen=True)
class AuthUser:
    uid: str
    role: str  # admin | transporter | factory | buyer


def _verify(token: str, project_id: str) -> dict:
    """Blocking: fetches Google's signing certs (cached). Run it in a thread."""
    return id_token.verify_firebase_token(
        token, google_requests.Request(), audience=project_id
    )


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(401, detail, headers={"WWW-Authenticate": "Bearer"})


async def current_user(
    db: DbSession,
    authorization: str | None = Header(default=None),
    x_dev_uid: str | None = Header(default=None),
) -> AuthUser:
    """Verify the caller and load their role. Local bypass: X-Dev-Uid picks a seeded user."""
    if auth_bypass_active():
        uid = x_dev_uid or DEV_ADMIN_UID
        if uid == DEV_ADMIN_UID:
            return AuthUser(uid, "admin")
    else:
        if not authorization or not authorization.lower().startswith("bearer "):
            raise _unauthorized("Missing bearer token")
        try:
            claims = await run_in_threadpool(
                _verify, authorization.split(" ", 1)[1].strip(), get_settings().firebase_project_id
            )
        except ValueError:
            raise _unauthorized("Invalid token") from None
        uid = claims.get("sub") or claims.get("user_id") or ""
    role = (await db.execute(select(User.role).where(User.uid == uid))).scalar_one_or_none()
    if role is None:
        raise HTTPException(403, "This account has no role; ask an admin to add it")
    return AuthUser(uid, role)


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
