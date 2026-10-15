"""Admin bootstrap: a verified email listed in BOOTSTRAP_ADMIN_EMAILS is an admin from the first
request, with no signup form. Nobody else can become admin by any route."""
import logging
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import bootstrap_admin_emails
from app.db_models.tables import User

if TYPE_CHECKING:
    from app.auth.firebase import Claims

log = logging.getLogger(__name__)


def is_bootstrap_admin(claims: "Claims") -> bool:
    return bool(
        claims.email_verified and claims.email and claims.email.lower() in bootstrap_admin_emails()
    )


async def ensure_bootstrap_admin(db: AsyncSession, claims: "Claims") -> User | None:
    """Create or promote the caller to an active admin when their verified email is listed.

    Returns the user, or None when the caller is not a bootstrap admin. The caller commits.
    """
    if not is_bootstrap_admin(claims):
        return None
    email = claims.email.lower()
    user = await db.get(User, claims.uid)
    if user is None:
        clash = (await db.execute(select(User.uid).where(User.email == email))).scalar_one_or_none()
        if clash is not None:  # the same email already belongs to a different login
            log.warning("Bootstrap admin email %s is already used by uid %s", email, clash)
            return None
        user = User(
            uid=claims.uid, role="admin", status="active", email=email,
            display_name=(claims.name or email.split("@")[0])[:80],
        )
        db.add(user)
    elif user.role != "admin" or user.status != "active":
        user.role, user.status = "admin", "active"
        user.email = user.email or email
    else:
        return user
    await db.flush()
    log.info("Granted admin to %s", email)
    return user
