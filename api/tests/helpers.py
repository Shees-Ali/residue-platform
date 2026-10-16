"""Constants and small helpers shared by the DB-backed flow tests."""
import uuid
from datetime import datetime, timedelta

from sqlalchemy import text

from app.services.lots import PKT

PRICE = 1_000_000_000  # paisa per tonne: ranks the test factory first, whatever is seeded
GROSS = 2_500_000_000  # 2.5 t at that price
TRANSPORTER_ESTIMATE = 500_000_000  # 20% of GROSS
FARMER_ESTIMATE = 1_750_000_000  # 70% of GROSS
PLATFORM_ESTIMATE = 250_000_000  # 10% of GROSS

ADMIN = {"X-Dev-Uid": "dev-admin"}
FACTORY = {"X-Dev-Uid": "t-factory"}
OTHER_FACTORY = {"X-Dev-Uid": "dev-factory-0"}
T1 = {"X-Dev-Uid": "t-trans1"}
T2 = {"X-Dev-Uid": "t-trans2"}
BUYER = {"X-Dev-Uid": "dev-buyer-0"}


def leg(path, weight_kg, **over):
    """A pickup or delivery body: the uploaded photo, the weight and where the truck is."""
    return {"photo_path": path, "weight_kg": weight_kg, "lat": 31.4, "lon": 74.38, **over}


def tomorrow() -> str:
    return (datetime.now(PKT).date() + timedelta(days=1)).isoformat()


async def scalar(api, sql, **params):
    return (await api.session.execute(text(sql), params)).scalar()


async def event_types(api, job_id=None) -> list[str]:
    """The event types recorded in this test, oldest first (all of them, or one job's)."""
    sql = "SELECT type FROM events WHERE created_at >= now()"
    params = {}
    if job_id is not None:
        sql += " AND job_id = :j"
        params["j"] = uuid.UUID(str(job_id))
    rows = await api.session.execute(text(sql + " ORDER BY created_at, id"), params)
    return [r[0] for r in rows]


async def offers_of(api, job_id):
    rows = await api.session.execute(
        text(
            "SELECT sequence, transporter_id, status, payout_amount FROM offers "
            "WHERE job_id = :j ORDER BY sequence"
        ),
        {"j": uuid.UUID(job_id)},
    )
    return [(r.sequence, str(r.transporter_id), r.status, r.payout_amount) for r in rows]


async def ledger_of(api, job_id) -> dict[str, int]:
    rows = await api.session.execute(
        text(
            "SELECT kind, sum(amount) AS total FROM ledger_entries WHERE job_id = :j GROUP BY kind"
        ),
        {"j": uuid.UUID(job_id)},
    )
    return {r.kind: int(r.total) for r in rows}


async def fund(api, world):
    r = await api.post(f"/api/jobs/{world.job_id}/fund", headers=FACTORY)
    assert r.status_code == 200, r.text
    return r.json()


async def accept_first_offer(api, world, headers=T1):
    offer = await scalar(
        api, "SELECT id FROM offers WHERE job_id = :j AND sequence = 1", j=uuid.UUID(world.job_id)
    )
    r = await api.post(f"/api/offers/{offer}/accept", headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


async def photo(api, world, kind, headers):
    """Ask for an upload URL, pretend the client uploaded bytes, return the object path."""
    r = await api.post(
        f"/api/jobs/{world.job_id}/photos/upload-url", headers=headers, json={"kind": kind}
    )
    assert r.status_code == 200, r.text
    path = r.json()["path"]
    api.storage.blobs[path] = b"fake-jpeg-bytes"
    return path


async def move_to_delivered(api, world, pickup_kg=2400, delivery_kg=2450):
    """fund -> accept -> pickup -> deliver, as the test factory and transporter 1."""
    await fund(api, world)
    await accept_first_offer(api, world)
    p = await photo(api, world, "pickup", T1)
    r = await api.post(
        f"/api/jobs/{world.job_id}/pickup",
        headers=T1,
        json=leg(p, pickup_kg),
    )
    assert r.status_code == 200, r.text
    d = await photo(api, world, "delivery", T1)
    r = await api.post(
        f"/api/jobs/{world.job_id}/deliver",
        headers=T1,
        json=leg(d, delivery_kg),
    )
    assert r.status_code == 200, r.text
    return r.json()


async def confirm(api, world, weight_kg=2500, headers=FACTORY):
    return await api.post(
        f"/api/jobs/{world.job_id}/confirm",
        headers=headers,
        json={"accept": True, "final_weight_kg": weight_kg},
    )


async def verification_call(api, world) -> str:
    r = await api.post(f"/api/jobs/{world.job_id}/verification-call")
    assert r.status_code == 200, r.text
    return r.json()["call_id"]


async def answer(api, call_id, world, confirmed: bool, key="v1", note=""):
    return await api.post(
        "/api/agent/confirmations",
        headers={"Idempotency-Key": key},
        json={"call_id": call_id, "job_id": world.job_id, "confirmed": confirmed, "note": note},
    )
