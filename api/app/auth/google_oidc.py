from fastapi import Header, HTTPException
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from starlette.concurrency import run_in_threadpool

from app.config import get_settings, voice_auth_bypass_active


def _verify(token: str, audience: str) -> dict:
    """Blocking: fetches Google's signing certs (cached). Run it in a thread."""
    return id_token.verify_oauth2_token(token, google_requests.Request(), audience=audience)


async def voice_service_caller(authorization: str | None = Header(default=None)) -> str:
    """Verify a Google ID token from the voice service; return its service account email."""
    if voice_auth_bypass_active():
        return "local-dev"
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=401, detail="Missing bearer token", headers={"WWW-Authenticate": "Bearer"}
        )
    settings = get_settings()
    try:
        claims = await run_in_threadpool(
            _verify, authorization.split(" ", 1)[1].strip(), settings.api_audience
        )
    except ValueError:
        raise HTTPException(
            status_code=401, detail="Invalid token", headers={"WWW-Authenticate": "Bearer"}
        ) from None
    email = claims.get("email")
    if (
        not settings.voice_service_account
        or email != settings.voice_service_account
        or not claims.get("email_verified")
    ):
        raise HTTPException(status_code=403, detail="Not the voice service account")
    return email
