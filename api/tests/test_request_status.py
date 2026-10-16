"""F5: what the voice agent tells a caller about their own requests."""
import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from sqlalchemy import text

from app.db_models.base import JOB_STATES, LOT_STATUSES
from app.services.request_status import RECENT, describe, stage
from tests.helpers import (
    FACTORY,
    FARMER_ESTIMATE,
    T1,
    accept_first_offer,
    answer,
    confirm,
    fund,
    leg,
    move_to_delivered,
    photo,
    tomorrow,
    verification_call,
)


def test_every_job_state_and_lot_status_has_a_specific_stage():
    for state in JOB_STATES:
        name, sentence = stage("assigned", state)
        assert name != "received", state  # a job always means more than "received"
        assert sentence.endswith("."), state
    for status in LOT_STATUSES:
        assert stage(status, None)[0] in {"received", "rejected"}
    assert stage("rejected", None)[0] == "rejected"
    assert stage("assigned", "settled")[0] == "paid"
    assert stage("assigned", "disputed")[0] == "on_hold"


def _row(*, job=None, pickup=True):
    created = datetime(2026, 10, 16, 21, 30, tzinfo=UTC)  # 02:30 on the 17th in Pakistan
    lot = SimpleNamespace(
        id=uuid.uuid4(), status="assigned" if job else "open", quantity_tonnes=2,
        village_name="Raiwind", district="Lahore", created_at=created,
        pickup_from=created if pickup else None, pickup_to=created if pickup else None,
    )
    return lot, job, None, "Wheat straw", "Test Factory"


def _job(state, **over):
    fields = dict(
        state=state, farmer_share_bps=7000, est_weight_kg=2500, quoted_price_per_tonne=1_000_000,
        final_weight_kg=None, rejection_reason=None,
    )
    return SimpleNamespace(**{**fields, **over})


def test_missing_pickup_times_do_not_break_the_answer():
    out = describe(_row(pickup=False))
    assert out["pickup_text"] is None and out["stage"] == "received"


def test_reported_on_is_the_pakistan_date():
    assert describe(_row())["reported_on"] == "2026-10-17"


def test_a_rejected_load_pays_nothing_and_says_why():
    out = describe(_row(job=_job("rejected", rejection_reason="Too wet")))
    assert out["farmer_amount_rupees"] == 0.0
    assert "est_farmer_amount_rupees" not in out
    assert out["rejection_reason"] == "Too wet"


def test_an_unverified_caller_hears_no_places_factory_or_money():
    out = describe(_row(job=_job("confirmed", final_weight_kg=2400)), full=False)
    assert set(out) == {
        "lot_id", "residue_label", "reported_on", "stage", "status_text", "details_withheld",
    }
    assert out["details_withheld"] is True


# --- through the real route (needs DATABASE_URL, like the other route tests) ----------------


async def status(api, call_id):
    r = await api.post("/api/agent/status", json={"call_id": call_id})
    assert r.status_code == 200, r.text
    return r.json()["requests"]


async def test_a_caller_hears_their_request_move_through_the_stages(api, world):
    [req] = await status(api, world.call_id)
    assert req["lot_id"] == world.lot_id
    assert req["stage"] == "matched"
    assert req["est_farmer_amount_rupees"] == FARMER_ESTIMATE / 100  # as the quote says
    assert "farmer_phone" not in req and "details_withheld" not in req

    await fund(api, world)
    assert (await status(api, world.call_id))[0]["stage"] == "finding_transporter"
    await accept_first_offer(api, world)
    assert (await status(api, world.call_id))[0]["stage"] == "transporter_coming"
    p = await photo(api, world, "pickup", T1)
    r = await api.post(f"/api/jobs/{world.job_id}/pickup", headers=T1, json=leg(p, 2400))
    assert r.status_code == 200, r.text
    assert (await status(api, world.call_id))[0]["stage"] == "on_the_way"


async def test_weighed_paid_and_disputed_amounts_match_settlement(api, world):
    await move_to_delivered(api, world)
    assert (await status(api, world.call_id))[0]["stage"] == "at_factory"
    await confirm(api, world, weight_kg=2000)
    [req] = await status(api, world.call_id)
    assert req["stage"] == "awaiting_your_confirmation"
    assert req["final_weight_kg"] == 2000
    assert req["farmer_amount_rupees"] == FARMER_ESTIMATE * 2000 / 2500 / 100  # 70% of 2 t
    call_id = await verification_call(api, world)
    assert (await answer(api, call_id, world, True)).status_code == 200
    [req] = await status(api, world.call_id)
    assert req["stage"] == "paid"
    paid = await api.session.execute(
        text("SELECT amount FROM ledger_entries WHERE job_id = :j AND kind = 'release_farmer'"),
        {"j": uuid.UUID(world.job_id)},
    )
    assert req["farmer_amount_rupees"] == paid.scalar() / 100  # exactly what was released


async def test_a_disputed_job_is_on_hold(api, world):
    await move_to_delivered(api, world)
    await confirm(api, world, weight_kg=2500)
    call_id = await verification_call(api, world)
    await answer(api, call_id, world, False, note="Weight is wrong")
    assert (await status(api, world.call_id))[0]["stage"] == "on_hold"


async def test_a_rejected_load_reports_no_payment(api, world):
    await move_to_delivered(api, world)
    r = await api.post(
        f"/api/jobs/{world.job_id}/confirm", headers=FACTORY,
        json={"accept": False, "reason": "Too wet to use"},
    )
    assert r.status_code == 200, r.text
    [req] = await status(api, world.call_id)
    assert req["stage"] == "rejected" and req["farmer_amount_rupees"] == 0.0
    assert req["rejection_reason"] == "Too wet to use"


async def test_only_the_callers_own_recent_requests_newest_first(api, world):
    other = await api.post(
        "/api/internal/calls", json={"twilio_call_sid": "CA-other", "caller_phone": "+923001112233"}
    )
    assert await status(api, other.json()["call_id"]) == []  # another farmer sees nothing

    created = []
    for i in range(RECENT + 1):
        r = await api.post(
            "/api/agent/lots",
            headers={"Idempotency-Key": f"many-{i}"},
            json={
                "call_id": world.call_id, "residue_type": "rice_straw", "quantity_tonnes": i + 1,
                "pickup_date": tomorrow(), "pickup_part": "morning",
                "village": "Raiwind", "district": "Lahore",
            },
        )
        assert r.status_code == 201, r.text
        created.append(r.json()["lot_id"])
    # one transaction gives every row the same now(): spread them out to test the order
    for i, lot_id in enumerate([world.lot_id, *created]):
        await api.session.execute(
            text("UPDATE lots SET created_at = now() + make_interval(secs => :i) WHERE id = :id"),
            {"i": i, "id": uuid.UUID(lot_id)},
        )
    requests = await status(api, world.call_id)
    assert [r["lot_id"] for r in requests] == created[::-1][:RECENT]  # newest first, 5 at most


async def test_a_typed_number_on_the_phone_page_hears_only_the_stage(api, world):
    browser = await api.post(
        "/api/internal/calls",
        json={"twilio_call_sid": f"web-{uuid.uuid4().hex}", "caller_phone": world.farmer_phone},
    )
    [req] = await status(api, browser.json()["call_id"])
    assert req["details_withheld"] is True and req["stage"] == "matched"
    assert not {"village", "district", "factory_name", "est_farmer_amount_rupees"} & set(req)
    # nor can the lot id it hears unlock the amounts through get_quote
    r = await api.post(
        "/api/agent/quote", json={"call_id": browser.json()["call_id"], "lot_id": req["lot_id"]}
    )
    assert r.status_code == 422 and r.json()["error"] == "unknown_lot", r.text
    assert (await api.post(
        "/api/agent/quote", json={"call_id": world.call_id, "lot_id": req["lot_id"]}
    )).status_code == 200  # the real phone call that made it still gets its quote
    made = await api.post(
        "/api/agent/lots",
        headers={"Idempotency-Key": "on-phone-page"},
        json={
            "call_id": browser.json()["call_id"], "residue_type": "rice_straw",
            "quantity_tonnes": 1, "pickup_date": tomorrow(), "pickup_part": "morning",
            "village": "Raiwind", "district": "Lahore",
        },
    )
    assert made.status_code == 201, made.text
    r = await api.post(
        "/api/agent/quote",
        json={"call_id": browser.json()["call_id"], "lot_id": made.json()["lot_id"]},
    )
    assert r.status_code == 200, r.text  # a lot made on this call can be quoted on it


@pytest.mark.parametrize("sid", [None, ""])
async def test_a_call_with_no_reference_is_treated_like_the_phone_page(api, world, sid):
    call_id = (
        await api.session.execute(
            text(
                "INSERT INTO calls (kind, farmer_id, twilio_call_sid) "
                "SELECT 'intake', farmer_id, :sid FROM calls WHERE id = :c RETURNING id"
            ),
            {"sid": sid, "c": uuid.UUID(world.call_id)},
        )
    ).scalar()
    [req] = await status(api, str(call_id))
    assert req["details_withheld"] is True
    r = await api.post("/api/agent/quote", json={"call_id": str(call_id), "lot_id": req["lot_id"]})
    assert r.status_code == 422 and r.json()["error"] == "unknown_lot", r.text


async def test_a_call_with_no_farmer_is_refused(api):
    call_id = (
        await api.session.execute(text("INSERT INTO calls (kind) VALUES ('intake') RETURNING id"))
    ).scalar()
    r = await api.post("/api/agent/status", json={"call_id": str(call_id)})
    assert r.status_code == 409


@pytest.mark.parametrize("call_id", [str(uuid.uuid4()), "not-a-uuid"])
async def test_unknown_calls_get_no_requests(api, call_id):
    r = await api.post("/api/agent/status", json={"call_id": call_id})
    assert r.status_code == 404
