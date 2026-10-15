"""M3: the farmer confirms or disputes on the web, the job ledger, payouts on the final weight."""
import uuid

from sqlalchemy import text

from tests.helpers import ADMIN, FACTORY, OTHER_FACTORY, T1, confirm, move_to_delivered, scalar

NOTE_HELP = "Tell us what is wrong (at least 3 characters)"


def who(uid, phone):
    return {"X-Dev-Uid": uid, "X-Dev-Phone": phone}


async def farmer_of(api, world, uid="f-owner"):
    h = who(uid, world.farmer_phone)
    r = await api.post(
        "/api/me/register", headers=h, json={"role": "farmer", "display_name": "Fatima Bibi"}
    )
    assert r.status_code == 201 and r.json()["farmer_linked"] is True, r.text
    return h


async def confirmed_job(api, world, weight_kg=2500):
    await move_to_delivered(api, world)
    r = await confirm(api, world, weight_kg=weight_kg)
    assert r.status_code == 200, r.text


async def verify(api, world, headers, confirmed=True, note=""):
    return await api.post(
        f"/api/jobs/{world.job_id}/verify",
        headers=headers,
        json={"confirmed": confirmed, "note": note},
    )


def fields(r):
    return {e["field"]: e["message"] for e in r.json()["errors"]}


async def kinds(api, world):
    rows = await api.session.execute(
        text("SELECT kind, amount FROM ledger_entries WHERE job_id = :j ORDER BY created_at"),
        {"j": uuid.UUID(world.job_id)},
    )
    return {r.kind: r.amount for r in rows}


# --- yes ---------------------------------------------------------------------------------


async def test_the_farmer_says_yes_and_the_job_settles_with_a_balanced_ledger(api, world):
    h = await farmer_of(api, world)
    await confirmed_job(api, world)
    r = await verify(api, world, h, True)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["state"] == "settled" and body["farmer_amount"] > 0
    ledger = await kinds(api, world)
    assert ledger["release_farmer"] == body["farmer_amount"] and "platform_fee" in ledger
    assert (await api.get("/api/ledger/check", headers=ADMIN)).json()["balanced"] is True
    paid = (await api.get("/api/ledger/mine", headers=h)).json()
    assert [(p["status"], p["amount"]) for p in paid] == [("released", body["farmer_amount"])]


async def test_saying_yes_twice_never_pays_twice(api, world):
    h = await farmer_of(api, world)
    await confirmed_job(api, world)
    assert (await verify(api, world, h, True)).status_code == 200
    again = await verify(api, world, h, True)
    assert again.status_code == 409
    count = await scalar(
        api, "SELECT count(*) FROM ledger_entries WHERE kind = 'release_farmer' AND job_id = :j",
        j=uuid.UUID(world.job_id),
    )
    assert count == 1


async def test_the_farmer_payout_estimate_follows_the_final_weight(api, world):
    h = await farmer_of(api, world)
    before = (await api.get("/api/ledger/mine", headers=h)).json()[0]["amount"]
    await confirmed_job(api, world, weight_kg=3000)  # heavier than the 2500 kg estimate
    after = (await api.get("/api/ledger/mine", headers=h)).json()[0]["amount"]
    job = (await api.get(f"/api/jobs/{world.job_id}", headers=h)).json()
    assert after > before and after == job["est_farmer_payout"]


# --- no ----------------------------------------------------------------------------------


async def test_a_dispute_freezes_the_money_and_reaches_the_admin_queue(api, world):
    h = await farmer_of(api, world)
    await confirmed_job(api, world)
    r = await verify(api, world, h, False, "The weight is much less than I loaded")
    assert r.status_code == 200 and r.json() == {
        "job_id": world.job_id, "state": "disputed", "farmer_amount": None,
    }
    assert "release_farmer" not in await kinds(api, world)
    queue = (await api.get("/api/escalations", headers=ADMIN)).json()
    item = next(e for e in queue if e["job_id"] == world.job_id)
    assert item["call_id"] is None and item["farmer_phone"] == world.farmer_phone
    assert "much less than I loaded" in item["summary"]
    resolve = await api.post(f"/api/escalations/{item['id']}/resolve", headers=ADMIN)
    assert resolve.status_code == 204


async def test_a_dispute_needs_a_reason_but_a_yes_does_not(api, world):
    h = await farmer_of(api, world)
    await confirmed_job(api, world)
    for note in ("", "  ", "no"):
        bad = await verify(api, world, h, False, note)
        assert bad.status_code == 422 and fields(bad) == {"note": NOTE_HELP}
    too_long = await verify(api, world, h, True, "x" * 1001)
    assert fields(too_long) == {"note": "Note must be at most 1000 characters"}
    assert (await verify(api, world, h, True, "")).status_code == 200


async def test_a_refused_answer_changes_nothing(api, world):
    h = await farmer_of(api, world)
    await confirmed_job(api, world)
    await verify(api, world, h, False, "")
    state = (await api.get(f"/api/jobs/{world.job_id}", headers=ADMIN)).json()["state"]
    assert state == "confirmed"
    assert await scalar(api, "SELECT count(*) FROM verifications") == 0


# --- who and when ----------------------------------------------------------------------------


async def test_only_the_owner_can_answer_and_only_after_the_factory_confirms(api, world):
    h = await farmer_of(api, world)
    stranger = who("f-stranger", "+923007770321")
    await api.post(
        "/api/me/register", headers=stranger, json={"role": "farmer", "display_name": "Other One"}
    )
    await move_to_delivered(api, world)
    early = await verify(api, world, h, True)
    assert early.status_code == 409
    assert "not waiting for your confirmation" in early.json()["detail"]
    await confirm(api, world)
    assert (await verify(api, world, stranger, True)).status_code == 404
    bad_id = await api.post("/api/jobs/not-a-uuid/verify", headers=h, json={"confirmed": True})
    assert bad_id.status_code == 404
    assert (await verify(api, world, T1, True)).status_code == 403


# --- the per-job ledger ------------------------------------------------------------------------


async def test_the_factory_and_admin_read_the_money_for_a_job(api, world):
    h = await farmer_of(api, world)
    await confirmed_job(api, world)
    await verify(api, world, h, True)
    url = f"/api/jobs/{world.job_id}/ledger"
    mine = (await api.get(url, headers=FACTORY)).json()
    wanted = {"escrow_in", "release_transporter", "release_farmer", "platform_fee"}
    assert {e["kind"] for e in mine} >= wanted
    assert len((await api.get(url, headers=ADMIN)).json()) == len(mine)
    assert (await api.get(url, headers=OTHER_FACTORY)).status_code == 404
    assert (await api.get(url, headers=T1)).status_code == 403
