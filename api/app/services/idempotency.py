"""Idempotent writes: the first request runs, replays return its stored response.

The key row is inserted in the same transaction as the work, so a failure rolls both back and
the caller can retry with the same key. Concurrent duplicates wait on the unique key, then replay.
"""
import hashlib
import json
from collections.abc import Awaitable, Callable

from fastapi import HTTPException
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db_models.tables import IdempotencyKey


def request_hash(payload: dict) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()


async def run_idempotent(
    db: AsyncSession,
    key: str,
    route: str,
    req_hash: str,
    work: Callable[[], Awaitable[tuple[int, dict]]],
) -> tuple[int, dict, bool]:
    """Return (status_code, body, replayed). The caller commits."""
    inserted = (
        await db.execute(
            insert(IdempotencyKey)
            .values(key=key, route=route, request_hash=req_hash)
            .on_conflict_do_nothing(index_elements=["key"])
            .returning(IdempotencyKey.key)
        )
    ).first()
    if inserted is None:
        row = (
            await db.execute(select(IdempotencyKey).where(IdempotencyKey.key == key))
        ).scalar_one()
        if row.route != route or row.request_hash != req_hash:
            raise HTTPException(409, "Idempotency-Key was already used for a different request")
        if row.response is None:
            raise HTTPException(409, "A request with this Idempotency-Key is still in progress")
        return row.status_code, row.response, True
    status, body = await work()
    await db.execute(
        update(IdempotencyKey)
        .where(IdempotencyKey.key == key)
        .values(status_code=status, response=body)
    )
    return status, body, False
