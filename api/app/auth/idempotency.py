from fastapi import Header, HTTPException


async def require_idempotency_key(idempotency_key: str | None = Header(default=None)) -> str:
    if not idempotency_key or not idempotency_key.strip():
        raise HTTPException(status_code=400, detail="Idempotency-Key header is required")
    # TODO(F1): store key + response so replays return the original result.
    return idempotency_key
