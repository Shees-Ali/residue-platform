from fastapi import Depends, Header, HTTPException


async def current_user(authorization: str | None = Header(default=None)) -> dict:
    """Verify a Firebase ID token and return its claims (incl. `role`)."""
    # TODO(A2): verify via google.oauth2.id_token.verify_firebase_token; reject if missing/invalid.
    raise HTTPException(status_code=501, detail="Firebase auth not implemented")


def require_role(*roles: str):
    async def checker(user: dict = Depends(current_user)) -> dict:
        if user.get("role") not in roles:
            raise HTTPException(status_code=403, detail="Forbidden")
        return user

    return checker
