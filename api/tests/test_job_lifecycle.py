"""T2, FA2, F2, F3, F4 and A3 through the real routes: a job from funded to settled.

Prices are chosen so every amount is an exact, easy number: 1,000,000,000 paisa per tonne,
2.5 t estimated, shares 70% farmer / 20% transporter / 10% platform.
"""
import uuid

from sqlalchemy import text

from tests.helpers import (
    ADMIN,
    FACTORY,
    FARMER_ESTIMATE,
    GROSS,
    OTHER_FACTORY,
    PLATFORM_ESTIMATE,
    T1,
    T2,
    TRANSPORTER_ESTIMATE,
    accept_first_offer,
    answer,
    confirm,
    fund,
    ledger_of,
    move_to_delivered,
    photo,
    scalar,
    verification_call,
)


async def quote(api, world):
    r = await api.post("/api/agent/quote", json={"call_id": world.call_id, "lot_id": world.lot_id})
    assert r.status_code == 200, r.text
    return r.json()


async def check(api):
    r = await api.get("/api/ledger/check")
    assert r.status_code == 200, r.text
    return r.json()


# --- the whole flow, and quote == ledger ---------------------------------------------------


async def test_a_job_runs_from_funded_to_settled_and_the_quote_matches_the_ledger(api, world):
    q = await quote(api, world)  # F2: what the farmer is told on the call
    assert (q["price_per_tonne"], q["farmer_share_percent"]) == (1_000_000_000, 70.0)
    assert (q["est_total"], q["est_farmer_amount"]) == (GROSS, FARMER_ESTIMATE)
    assert q["farmer_per_tonne_rupees"] == 7_000_000.0
    assert "confirm" in q["payment_timing"]

    delivered = await move_to_delivered(api, world)
    assert delivered["state"] == "delivered"

    # T2: the payout is pending until the factory confirms
    pending = (await api.get("/api/ledger/mine", headers=T1)).json()
    assert [(p["status"], p["amount"]) for p in pending] == [("pending", TRANSPORTER_ESTIMATE)]

    # FA2: an AI grade helps, and is labelled an estimate
    graded = await api.post(f"/api/jobs/{world.job_id}/grade", headers=FACTORY, json={})
    assert graded.status_code == 200, graded.text
    assert graded.json()["is_estimate"] is True
    assert "weighbridge" in graded.json()["grade"]["disclaimer"].lower()
    assert api.grader.calls == 1

    confirmed = await confirm(api, world, weight_kg=2500)
    assert confirmed.status_code == 200 and confirmed.json()["state"] == "confirmed"
    assert confirmed.json()["final_weight_kg"] == 2500
    released = (await api.get("/api/ledger/mine", headers=T1)).json()
    assert [(p["status"], p["amount"]) for p in released] == [("released", TRANSPORTER_ESTIMATE)]

    # F4: the farmer says yes on the verification call
    call_id = await verification_call(api, world)
    settled = await answer(api, call_id, world, True)
    assert settled.status_code == 200, settled.text
    assert settled.json()["state"] == "settled"
    assert settled.json()["farmer_amount"] == FARMER_ESTIMATE

    ledger = await ledger_of(api, world.job_id)
    assert ledger == {
        "escrow_in": GROSS,
        "release_transporter": TRANSPORTER_ESTIMATE,
        "release_farmer": q["est_farmer_amount"],  # the quote is what the ledger paid
        "platform_fee": PLATFORM_ESTIMATE,
    }
    # A3: escrow in equals everything released, on screen and in the view
    report = await check(api)
    assert report["balanced"] and report["jobs_checked"] == 1 and report["unbalanced_jobs"] == []
    assert report["held_in_escrow"] == 0
    view = await scalar(
        api, "SELECT balanced FROM ledger_balance WHERE job_id = :j", j=uuid.UUID(world.job_id)
    )
    assert view is True

    # ... and the impact counter rose at settlement, with a record per lot
    impact = (await api.get("/api/impact")).json()
    assert (impact["tonnes_diverted"], impact["jobs_settled"]) == (2.5, 1)
    assert (impact["records"][0]["village"], impact["records"][0]["district"]) == (
        "Raiwind", "Lahore",
    )
    assert impact["records"][0]["weight_kg"] == 2500


async def test_a_heavier_weighbridge_weight_tops_up_escrow_and_still_balances(api, world):
    await move_to_delivered(api, world)
    assert (await confirm(api, world, weight_kg=2600)).status_code == 200
    await answer(api, await verification_call(api, world), world, True)
    ledger = await ledger_of(api, world.job_id)
    assert ledger["escrow_in"] == 2_600_000_000  # 2.5 bn funded + 0.1 bn top-up
    assert ledger["release_transporter"] == 520_000_000
    assert ledger["release_farmer"] == 1_820_000_000
    assert ledger["platform_fee"] == 260_000_000
    assert "refund" not in ledger
    assert (await check(api))["balanced"]


async def test_a_lighter_weight_refunds_the_difference_and_still_balances(api, world):
    await move_to_delivered(api, world)
    assert (await confirm(api, world, weight_kg=2000)).status_code == 200
    await answer(api, await verification_call(api, world), world, True)
    ledger = await ledger_of(api, world.job_id)
    assert ledger["refund"] == 500_000_000
    assert (ledger["release_transporter"], ledger["release_farmer"], ledger["platform_fee"]) == (
        400_000_000, 1_400_000_000, 200_000_000,
    )
    assert (await check(api))["balanced"]


# --- FA2 rejection ---------------------------------------------------------------------------


async def test_rejecting_a_lot_needs_a_reason_and_applies_the_cost_rule(api, world):
    await move_to_delivered(api, world)
    url = f"/api/jobs/{world.job_id}/confirm"
    assert (await api.post(url, headers=FACTORY, json={"accept": False})).status_code == 422
    rejected = await api.post(
        url, headers=FACTORY, json={"accept": False, "reason": "wet, full of soil"}
    )
    assert rejected.status_code == 200, rejected.text
    assert (rejected.json()["state"], rejected.json()["rejection_reason"]) == (
        "rejected", "wet, full of soil",
    )
    ledger = await ledger_of(api, world.job_id)
    # the transporter still gets their estimated share; the rest of escrow goes back
    assert ledger == {
        "escrow_in": GROSS,
        "release_transporter": TRANSPORTER_ESTIMATE,
        "refund": GROSS - TRANSPORTER_ESTIMATE,
    }
    assert await scalar(api, "SELECT status FROM lots WHERE id = :l", l=uuid.UUID(world.lot_id)) \
        == "rejected"
    assert (await check(api))["balanced"]


# --- F4 dispute ------------------------------------------------------------------------------


async def test_a_dispute_freezes_the_payout_and_alerts_the_admin(api, world):
    await move_to_delivered(api, world)
    await confirm(api, world, weight_kg=2500)
    call_id = await verification_call(api, world)
    r = await answer(api, call_id, world, False, note="the weight sounds too low")
    assert r.status_code == 200 and r.json()["state"] == "disputed"

    ledger = await ledger_of(api, world.job_id)
    assert "release_farmer" not in ledger and "platform_fee" not in ledger  # frozen
    assert ledger == {"escrow_in": GROSS, "release_transporter": TRANSPORTER_ESTIMATE}
    assert (await check(api))["held_in_escrow"] == GROSS - TRANSPORTER_ESTIMATE

    queue = (await api.get("/api/escalations")).json()
    mine = [e for e in queue if world.job_id in e["summary"]]
    assert len(mine) == 1 and "too low" in mine[0]["summary"]
    assert mine[0]["farmer_phone"] == world.farmer_phone
    assert "escalation.created" in [e["type"] for e in api.events.sent]

    # the farmer cannot flip a frozen job to yes afterwards
    assert (await answer(api, call_id, world, True, key="v2")).status_code == 409
    assert (await api.post(f"/api/escalations/{mine[0]['id']}/resolve")).status_code == 204
    assert (await api.post(f"/api/escalations/{mine[0]['id']}/resolve")).status_code == 409
    assert world.job_id not in str((await api.get("/api/escalations")).json())


# --- guards ----------------------------------------------------------------------------------


async def test_only_the_assigned_transporter_can_record_pickup_and_delivery(api, world):
    await fund(api, world)
    url = f"/api/jobs/{world.job_id}/pickup"
    path = f"jobs/{world.job_id}/pickup/x.jpg"
    body = {"photo_path": path, "weight_kg": 2400}
    assert (await api.post(url, headers=T1, json=body)).status_code == 404  # not accepted yet
    refused = await api.post(f"/api/jobs/{world.job_id}/photos/upload-url", headers=T1,
                             json={"kind": "pickup"})
    assert refused.status_code == 404  # no upload URL for a job that is not yours
    await accept_first_offer(api, world)
    path = await photo(api, world, "pickup", T1)
    body = {"photo_path": path, "weight_kg": 2400}
    assert (await api.post(url, headers=T2, json=body)).status_code == 404  # someone else's job
    assert (await api.post(f"/api/jobs/{world.job_id}/deliver", headers=T1,
                           json={"photo_path": path, "weight_kg": 2400})).status_code == 422
    assert (await api.post(url, headers=T1, json=body)).status_code == 200
    assert (await api.post(url, headers=T1, json=body)).status_code == 409  # only once


async def test_photo_paths_and_weights_are_checked(api, world):
    await fund(api, world)
    await accept_first_offer(api, world)
    url = f"/api/jobs/{world.job_id}/pickup"
    other_job = f"jobs/{uuid.uuid4()}/pickup/x.jpg"
    wrong_kind = f"jobs/{world.job_id}/delivery/x.jpg"
    for path in (other_job, wrong_kind, "anything.jpg"):
        r = await api.post(url, headers=T1, json={"photo_path": path, "weight_kg": 100})
        assert r.status_code == 422, path
    good = await photo(api, world, "pickup", T1)
    for weight in (0, -5, 100_001):
        r = await api.post(url, headers=T1, json={"photo_path": good, "weight_kg": weight})
        assert r.status_code == 422, weight
    # roles may only upload the photos that belong to them
    r = await api.post(f"/api/jobs/{world.job_id}/photos/upload-url", headers=T1,
                       json={"kind": "weighbridge"})
    assert r.status_code == 403
    r = await api.post(f"/api/jobs/{world.job_id}/photos/upload-url", headers=FACTORY,
                       json={"kind": "pickup"})
    assert r.status_code == 403


async def test_confirm_needs_the_right_factory_state_and_a_weight(api, world):
    url = f"/api/jobs/{world.job_id}/confirm"
    await move_to_delivered(api, world)
    assert (await api.post(url, headers=OTHER_FACTORY, json={"accept": True,
            "final_weight_kg": 2500})).status_code == 404
    assert (await api.post(url, headers=FACTORY, json={"accept": True})).status_code == 422
    assert (await confirm(api, world, weight_kg=0)).status_code == 422
    assert (await confirm(api, world, weight_kg=2500)).status_code == 200
    assert (await confirm(api, world, weight_kg=2500)).status_code == 409  # not delivered anymore


async def test_a_lot_can_only_be_graded_once_delivered_and_with_an_uploaded_photo(api, world):
    url = f"/api/jobs/{world.job_id}/grade"
    await fund(api, world)
    assert (await api.post(url, headers=FACTORY, json={})).status_code == 409  # not delivered
    await accept_first_offer(api, world)
    p = await photo(api, world, "pickup", T1)
    await api.post(f"/api/jobs/{world.job_id}/pickup", headers=T1,
                   json={"photo_path": p, "weight_kg": 2400})
    d = await photo(api, world, "delivery", T1)
    await api.post(f"/api/jobs/{world.job_id}/deliver", headers=T1,
                   json={"photo_path": d, "weight_kg": 2450})
    api.storage.blobs.clear()  # the client never actually uploaded the bytes
    assert (await api.post(url, headers=FACTORY, json={})).status_code == 422
    wb = await photo(api, world, "weighbridge", FACTORY)
    ok = await api.post(url, headers=FACTORY, json={"photo_path": wb})
    assert ok.status_code == 200 and ok.json()["grade"]["moisture_band"] == "dry"
    other = f"jobs/{uuid.uuid4()}/weighbridge/x.jpg"
    bad = await api.post(url, headers=FACTORY, json={"photo_path": other})
    assert bad.status_code == 422


async def test_grading_says_so_when_gemini_is_not_configured(api, world, monkeypatch):
    import app.services.grading as grading
    from app.main import app

    await move_to_delivered(api, world)
    app.dependency_overrides.pop(grading.get_grader)  # the real dependency, with no key set
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setattr(grading, "_grader", None)
    r = await api.post(f"/api/jobs/{world.job_id}/grade", headers=FACTORY, json={})
    assert r.status_code == 503


# --- F2 / F4 identity and replay ----------------------------------------------------------


async def test_a_farmer_cannot_quote_or_verify_someone_elses_lot(api, world):
    other = await api.post("/api/internal/calls",
                           json={"twilio_call_sid": "CA-other", "caller_phone": "+923008880099"})
    r = await api.post("/api/agent/quote",
                       json={"call_id": other.json()["call_id"], "lot_id": world.lot_id})
    assert r.status_code == 422 and r.json()["error"] == "unknown_lot"

    await move_to_delivered(api, world)
    await confirm(api, world, weight_kg=2500)
    # an intake call (not a verification call) cannot settle money
    assert (await answer(api, world.call_id, world, True)).status_code == 404
    # another farmer's verification call cannot settle this job
    farmer = await scalar(api, "SELECT id FROM farmers WHERE phone = '+923008880099'")
    foreign = await scalar(
        api,
        "INSERT INTO calls (farmer_id, kind) VALUES (:f, 'verification') RETURNING id",
        f=farmer,
    )
    assert (await answer(api, str(foreign), world, True, key="v9")).status_code == 404
    assert "release_farmer" not in await ledger_of(api, world.job_id)


async def test_verification_only_works_on_a_confirmed_job_and_replays_do_not_pay_twice(api, world):
    await move_to_delivered(api, world)
    early = await api.post(f"/api/jobs/{world.job_id}/verification-call")
    assert early.status_code == 409  # not confirmed yet
    await confirm(api, world, weight_kg=2500)
    call_id = await verification_call(api, world)
    first = await answer(api, call_id, world, True, key="same")
    again = await answer(api, call_id, world, True, key="same")
    assert first.json() == again.json()
    paid = await scalar(
        api, "SELECT count(*) FROM ledger_entries WHERE job_id = :j AND kind = 'release_farmer'",
        j=uuid.UUID(world.job_id),
    )
    assert paid == 1
    no_key = await api.post("/api/agent/confirmations",
                            json={"call_id": call_id, "job_id": world.job_id, "confirmed": True})
    assert no_key.status_code == 400


async def test_no_quote_when_no_factory_accepts_the_residue(api, world):
    await api.session.execute(text("INSERT INTO residue_types VALUES ('x_none', 'Unwanted')"))
    from tests.helpers import tomorrow

    lot = await api.post("/api/lots", json={
        "farmer_phone": world.farmer_phone, "residue_type": "x_none", "quantity_tonnes": 1,
        "pickup_date": tomorrow(), "pickup_part": "morning", "village": "Raiwind",
        "district": "Lahore"})
    assert lot.status_code == 201
    r = await api.post("/api/agent/quote",
                       json={"call_id": world.call_id, "lot_id": lot.json()["lot_id"]})
    assert r.status_code == 422 and r.json()["error"] == "no_factory_yet"


# --- F3 escalation queue -----------------------------------------------------------------


async def test_an_escalation_reaches_the_admin_queue_and_can_be_resolved(api, world):
    body = {"call_id": world.call_id, "summary": "Farmer is upset about the price",
            "transcript": "..."}
    r = await api.post("/api/agent/escalations", headers={"Idempotency-Key": "esc-1"}, json=body)
    assert r.status_code == 201 and r.json()["status"] == "open"
    replay = await api.post("/api/agent/escalations", headers={"Idempotency-Key": "esc-1"},
                            json=body)
    assert replay.json() == r.json()

    assert (await api.get("/api/escalations", headers=FACTORY)).status_code == 403
    queue = (await api.get("/api/escalations")).json()
    assert [e["summary"] for e in queue] == ["Farmer is upset about the price"]
    assert queue[0]["farmer_phone"] == world.farmer_phone
    assert [e["type"] for e in api.events.sent].count("escalation.created") == 1

    assert (await api.post(f"/api/escalations/{queue[0]['id']}/resolve")).status_code == 204
    assert (await api.get("/api/escalations")).json() == []
    resolved = (await api.get("/api/escalations?status=resolved")).json()
    assert len(resolved) == 1


async def test_escalating_needs_a_real_call(api):
    r = await api.post("/api/agent/escalations", headers={"Idempotency-Key": "e"},
                       json={"call_id": str(uuid.uuid4()), "summary": "x"})
    assert r.status_code == 404


async def test_ledger_listing_is_admin_only_and_filterable(api, world):
    await fund(api, world)
    listed = (await api.get(f"/api/ledger?job_id={world.job_id}")).json()
    assert [(e["kind"], e["amount"]) for e in listed] == [("escrow_in", GROSS)]
    assert (await api.get("/api/ledger", headers=FACTORY)).status_code == 403
    assert (await api.get("/api/ledger?kind=refund&limit=5")).status_code == 200
    assert (await api.get("/api/ledger?job_id=not-a-uuid")).status_code == 404
    assert (await api.get("/api/ledger/check", headers=ADMIN)).json()["held_in_escrow"] == GROSS
