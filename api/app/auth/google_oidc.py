from fastapi import Header, HTTPException


async def voice_service_caller(authorization: str | None = Header(default=None)) -> str:
    """Verify a Google ID token from the voice service; return its service account email."""
    # TODO(F1): verify with google.oauth2.id_token.verify_oauth2_token(audience=API_AUDIENCE)
    # and require email == settings.voice_service_account.
    raise HTTPException(status_code=501, detail="Google ID token auth not implemented")
