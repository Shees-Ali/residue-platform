"""F1 end to end through the real routes. DB-backed: skipped without DATABASE_URL, rolled back."""
import os
import uuid
from datetime import datetime, timedelta

import pytest
from sqlalchemy import func, select, text

from app.db_models.tables import Call, Job, Lot
from app.services.lots import PKT
from tests.helpers import event_types

pytestmark = pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL not set")

PHONE = "+923009990001"


def tomorrow() -> str:
    return (datetime.now(PKT).date() + timedelta(days=1)).isoformat()


def lot_body(call_id: str, **over) -> dict:
    body = {
        "call_id": call_id,
        "residue_type": "rice_straw",
        "quantity_tonnes": 2.5,
        "pickup_date": tomorrow(),
        "pickup_part": "morning",
        "village": "Raiwind",
        "district": "Lahore",
    }
    return body | over


async def start_call(api, sid="CA-test-1", phone=PHONE) -> str:
    r = await api.post(
        "/api/internal/calls", json={"twilio_call_sid": sid, "caller_phone": phone}
    )
    assert r.status_code == 200, r.text
    return r.json()["call_id"]


async def post_lot(api, call_id, key="k1", **over):
    return await api.post(
        "/api/agent/lots", json=lot_body(call_id, **over), headers={"Idempotency-Key": key}
    )


# --- internal call routes ----------------------------------------------------


async def test_start_call_creates_farmer_once_and_each_call_connects_once(api):
    first = await start_call(api)
    replay = await api.post(
        "/api/internal/calls", json={"twilio_call_sid": "CA-test-1", "caller_phone": PHONE}
    )
    assert replay.status_code == 409  # a replayed stream cannot attach to a live call
    other_sid = await start_call(api, sid="CA-test-2")
    assert first != other_sid
    farmers = (
        await api.session.execute(
            text("SELECT count(*) FROM farmers WHERE phone = :p"), {"p": PHONE}
        )
    ).scalar()
    assert farmers == 1  # the second call from the same number links the same farmer


async def test_start_call_rejects_bad_phone(api):
    r = await api.post(
        "/api/internal/calls", json={"twilio_call_sid": "x", "caller_phone": "0300-1234"}
    )
    assert r.status_code == 422


async def test_end_call_stores_summary_and_unknown_call_is_404(api):
    call_id = await start_call(api)
    r = await api.post(
        f"/api/internal/calls/{call_id}/end",
        json={"status": "completed", "summary": "reported rice straw"},
    )
    assert r.status_code == 200
    call = (
        await api.session.execute(select(Call).where(Call.id == uuid.UUID(call_id)))
    ).scalar_one()
    assert (call.status, call.summary) == ("completed", "reported rice straw")
    missing = await api.post(f"/api/internal/calls/{uuid.uuid4()}/end", json={})
    assert missing.status_code == 404


# --- create_lot --------------------------------------------------------------


async def test_create_lot_saves_a_complete_lot_and_returns_the_readback(api):
    call_id = await start_call(api)
    r = await post_lot(api, call_id)
    assert r.status_code == 201, r.text
    body = r.json()
    assert (body["residue_label"], body["village"], body["district"]) == (
        "Rice straw", "Raiwind", "Lahore",
    )
    assert body["place_match"] == "exact"
    assert body["quantity_tonnes"] == 2.5
    assert "06:00 to 12:00" in body["pickup_text"]

    lot = (
        await api.session.execute(select(Lot).where(Lot.id == uuid.UUID(body["lot_id"])))
    ).scalar_one()
    for col in Lot.__table__.columns:
        assert getattr(lot, col.key) is not None, f"lots.{col.key} is empty"
    assert lot.status == "assigned"  # A1 ran in the same transaction
    job = (await api.session.execute(select(Job).where(Job.lot_id == lot.id))).scalar_one()
    assert (job.state, job.est_weight_kg, job.farmer_share_bps) == ("created", 2500, 7000)
    assert str(lot.call_id) == call_id
    farmer_of_call = (
        await api.session.execute(select(Call.farmer_id).where(Call.id == uuid.UUID(call_id)))
    ).scalar_one()
    assert lot.farmer_id == farmer_of_call  # identity came from the call record
    assert await event_types(api) == ["lot.created", "lot.matched"]


async def test_replay_with_same_key_returns_the_same_lot_and_inserts_once(api):
    call_id = await start_call(api)
    before = (await api.session.execute(select(func.count()).select_from(Lot))).scalar()
    first = await post_lot(api, call_id, key="same")
    second = await post_lot(api, call_id, key="same")
    assert second.status_code == 201
    assert first.json() == second.json()
    count = (await api.session.execute(select(func.count()).select_from(Lot))).scalar()
    assert count == before + 1  # other lots may already exist in the local database
    assert await event_types(api) == ["lot.created", "lot.matched"]  # a replay adds none


async def test_same_key_with_a_different_payload_is_409(api):
    call_id = await start_call(api)
    assert (await post_lot(api, call_id, key="dup")).status_code == 201
    r = await post_lot(api, call_id, key="dup", quantity_tonnes=9)
    assert r.status_code == 409


async def test_missing_idempotency_key_is_400(api):
    call_id = await start_call(api)
    r = await api.post("/api/agent/lots", json=lot_body(call_id))
    assert r.status_code == 400


async def test_unknown_call_is_404_and_unlinked_call_is_409(api):
    r = await post_lot(api, str(uuid.uuid4()))
    assert r.status_code == 404
    orphan = Call(twilio_call_sid="CA-orphan")
    api.session.add(orphan)
    await api.session.flush()
    r = await post_lot(api, str(orphan.id))
    assert r.status_code == 409


@pytest.mark.parametrize(
    ("over", "error"),
    [
        ({"residue_type": "gold"}, "unknown_residue_type"),
        ({"district": "Atlantis"}, "unknown_district"),
        ({"quantity_tonnes": 0}, "invalid_quantity"),
        ({"pickup_part": "noon"}, "invalid_pickup_part"),
        ({"pickup_date": "2020-01-01"}, "pickup_date_in_past"),
    ],
)
async def test_fixable_input_returns_422_with_what_is_valid(api, over, error):
    call_id = await start_call(api)
    r = await post_lot(api, call_id, key=f"k-{error}", **over)
    assert r.status_code == 422
    assert r.json()["error"] == error
    assert "message" in r.json()


async def test_unknown_residue_lists_the_valid_codes(api):
    call_id = await start_call(api)
    r = await post_lot(api, call_id, residue_type="gold")
    assert "rice_straw" in r.json()["valid"]


async def test_unknown_village_falls_back_to_the_district_centroid(api):
    call_id = await start_call(api)
    r = await post_lot(api, call_id, village="Chak 99 Unknown")
    assert r.status_code == 201
    assert r.json()["place_match"] == "district"
    lot = (
        await api.session.execute(select(Lot).where(Lot.id == uuid.UUID(r.json()["lot_id"])))
    ).scalar_one()
    assert (lot.lat, lot.lon) == (31.52, 74.36) and lot.village_id is None


async def test_an_ended_call_cannot_be_restarted(api):
    call_id = await start_call(api, sid="CA-ended")
    await api.post(f"/api/internal/calls/{call_id}/end", json={"status": "completed"})
    r = await api.post(
        "/api/internal/calls", json={"twilio_call_sid": "CA-ended", "caller_phone": PHONE}
    )
    assert r.status_code == 409
