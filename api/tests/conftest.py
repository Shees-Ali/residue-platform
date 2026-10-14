import os
import uuid
from types import SimpleNamespace

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.main import app
from tests.helpers import PRICE, scalar, tomorrow


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
async def api(monkeypatch):
    """HTTP client wired to the real app and the local Postgres, rolled back after each test.

    Route code commits; the session uses savepoint mode so those commits release a savepoint and
    the outer transaction is rolled back at the end. Auth runs in local-bypass mode: pick who you
    are with the X-Dev-Uid header (default: the dev admin). Events go to `api.events`, photos to
    `api.storage` and AI grading is a canned estimate from `api.grader`.
    """
    if not os.getenv("DATABASE_URL"):
        pytest.skip("DATABASE_URL not set")
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
    from sqlalchemy.pool import NullPool

    from app.config import get_settings
    from app.db import async_url, get_session
    from app.services.events import FakeEvents, get_events
    from app.services.grading import Grade, get_grader
    from app.services.storage import FakeStorage, get_storage

    class CannedGrader:
        def __init__(self) -> None:
            self.calls = 0

        async def grade(self, images):
            self.calls += 1
            return Grade(
                residue_type="rice_straw",
                moisture_band="dry",
                contamination_flags=["soil"],
                confidence=0.82,
            )

    monkeypatch.setenv("AUTH_DISABLED", "true")
    monkeypatch.delenv("K_SERVICE", raising=False)
    engine = create_async_engine(async_url(get_settings().database_url), poolclass=NullPool)
    conn = await engine.connect()
    outer = await conn.begin()
    session = AsyncSession(
        bind=conn, join_transaction_mode="create_savepoint", expire_on_commit=False
    )
    events, storage, grader = FakeEvents(), FakeStorage(), CannedGrader()

    async def session_override():
        yield session

    app.dependency_overrides[get_session] = session_override
    app.dependency_overrides[get_events] = lambda: events
    app.dependency_overrides[get_storage] = lambda: storage
    app.dependency_overrides[get_grader] = lambda: grader
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
        c.events, c.session, c.storage, c.grader = events, session, storage, grader
        yield c
    app.dependency_overrides.clear()
    await session.close()
    await outer.rollback()
    await conn.close()
    await engine.dispose()


@pytest.fixture
async def world(api):
    """A factory that outranks the seeded ones, two transporters at the pickup, one assigned lot."""
    s = api.session

    async def one(sql, **params):
        return (await s.execute(text(sql), params)).scalar()

    # only the test transporters may be offered jobs, so the ladder is predictable
    await s.execute(text("UPDATE transporters SET approved_at = NULL"))
    for uid, role in (
        ("t-factory", "factory"),
        ("t-trans1", "transporter"),
        ("t-trans2", "transporter"),
    ):
        await s.execute(
            text("INSERT INTO users (uid, role) VALUES (:u, :r)"), {"u": uid, "r": role}
        )
    factory_id = await one(
        "INSERT INTO factories (name, lat, lon, price_per_tonne, user_uid) "
        "VALUES ('Test Factory', 31.4, 74.38, :p, 't-factory') RETURNING id",
        p=PRICE,
    )
    await s.execute(
        text("INSERT INTO factory_residues VALUES (:f, 'rice_straw')"), {"f": factory_id}
    )
    transporters = []
    for uid, lat, lon in (("t-trans1", 31.4, 74.38), ("t-trans2", 31.45, 74.40)):
        transporters.append(
            await one(
                "INSERT INTO transporters (phone, lat, lon, max_tonnes, approved_at, user_uid) "
                "VALUES (:ph, :lat, :lon, 10, now(), :u) RETURNING id",
                ph=f"+9230000{uid[-1]}0000", lat=lat, lon=lon, u=uid,
            )
        )

    phone = "+923008880001"
    call = await api.post(
        "/api/internal/calls", json={"twilio_call_sid": "CA-flow", "caller_phone": phone}
    )
    call_id = call.json()["call_id"]
    lot = await api.post(
        "/api/agent/lots",
        headers={"Idempotency-Key": "flow-1"},
        json={
            "call_id": call_id, "residue_type": "rice_straw", "quantity_tonnes": 2.5,
            "pickup_date": tomorrow(), "pickup_part": "morning",
            "village": "Raiwind", "district": "Lahore",
        },
    )
    assert lot.status_code == 201, lot.text
    lot_id = lot.json()["lot_id"]
    job_id = await scalar(api, "SELECT id FROM jobs WHERE lot_id = :l", l=uuid.UUID(lot_id))
    return SimpleNamespace(
        lot_id=lot_id,
        job_id=str(job_id),
        call_id=call_id,
        farmer_phone=phone,
        factory_id=str(factory_id),
        t1_id=str(transporters[0]),
        t2_id=str(transporters[1]),
    )
