"""Routers get a DB session and an events sink; identity comes from the call record."""
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from app.main import app
from app.routers.agent import farmer_id_for_call


def _session_returning(row):
    result = MagicMock()
    result.first.return_value = row
    session = MagicMock()
    session.execute = AsyncMock(return_value=result)
    return session


async def test_farmer_comes_from_the_call_record():
    farmer = uuid.uuid4()
    got = await farmer_id_for_call(_session_returning((farmer,)), str(uuid.uuid4()))
    assert got == farmer


@pytest.mark.parametrize("call_id", ["not-a-uuid", ""])
async def test_malformed_call_id_is_unknown(call_id):
    with pytest.raises(HTTPException) as e:
        await farmer_id_for_call(_session_returning(None), call_id)
    assert e.value.status_code == 404


async def test_missing_call_is_unknown():
    with pytest.raises(HTTPException) as e:
        await farmer_id_for_call(_session_returning(None), str(uuid.uuid4()))
    assert e.value.status_code == 404


async def test_call_without_a_linked_farmer_is_a_conflict():
    with pytest.raises(HTTPException) as e:
        await farmer_id_for_call(_session_returning((None,)), str(uuid.uuid4()))
    assert e.value.status_code == 409


def test_get_session_is_503_when_database_not_configured(monkeypatch, client):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    import app.db as db

    monkeypatch.setattr(db, "_engine", None)
    monkeypatch.setattr(db, "get_settings", lambda: MagicMock(database_url=""))
    from app.auth.firebase import current_user

    app.dependency_overrides[current_user] = lambda: {"role": "admin"}
    try:
        assert client.get("/api/lots").status_code == 503
    finally:
        app.dependency_overrides.clear()

