"""Who may call POST /api/dispatch/tick: Cloud Scheduler's service account, or an admin."""
import os

from fastapi import Header, HTTPException
from starlette.concurrency import run_in_threadpool

from app.auth import google_oidc
from app.auth.firebase import AuthUser, current_user
from app.config import get_settings
from app.deps import DbSession


async def scheduler_or_admin(
    db: DbSession,
    authorization: str | None = Header(default=None),
    x_dev_uid: str | None = Header(default=None),
) -> AuthUser:
    """Scheduler OIDC token (SCHEDULER_SERVICE_ACCOUNT) first, then a signed-in admin.

    The scheduler gets a synthetic admin identity with uid "scheduler" and may not use `force`.
    """
    scheduler = os.getenv("SCHEDULER_SERVICE_ACCOUNT", "")
    if scheduler and authorization and authorization.lower().startswith("bearer "):
        try:
            claims = await run_in_threadpool(
                google_oidc._verify,
                authorization.split(" ", 1)[1].strip(),
                get_settings().api_audience,
            )
        except ValueError:
            claims = {}
        if claims.get("email") == scheduler and claims.get("email_verified"):
            return AuthUser("scheduler", "scheduler")
    user = await current_user(db, authorization, x_dev_uid)
    if user.role != "admin":
        raise HTTPException(403, "Forbidden")
    return user
