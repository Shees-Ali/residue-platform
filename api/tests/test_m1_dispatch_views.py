"""M1: richer job views, who sees the farmer contact, decline, the ladder view, stats, the loop."""
from datetime import UTC, datetime, timedelta

from sqlalchemy import text

from app.services.dispatch_loop import loop_seconds, run_once
from tests.helpers import (
    ADMIN,
    FACTORY,
    FARMER_ESTIMATE,
    GROSS,
    T1,
    T2,
    TRANSPORTER_ESTIMATE,
    event_types,
    offers_of,
)


async def fund(api, world):
    r = await api.post(f"/api/jobs/{world.job_id}/fund", headers=FACTORY)
    assert r.status_code == 200, r.text
    return r.json()


async def offer_id_for(api, headers):
    offers = (await api.get("/api/offers", headers=headers)).json()
    return next(o["id"] for o in offers if o["status"] == "pending")


# --- the job read model -------------------------------------------------------------------


async def test_a_job_carries_coordinates_the_escrow_and_the_expected_payouts(api, world):
    job = (await api.get(f"/api/jobs/{world.job_id}", headers=ADMIN)).json()
    assert job["pickup_lat"] and job["factory_lat"] and job["pickup_lon"] and job["factory_lon"]
    assert job["escrow_amount"] == GROSS
    assert job["est_farmer_payout"] == FARMER_ESTIMATE
    assert job["est_transporter_payout"] == TRANSPORTER_ESTIMATE
    assert (job["village"], job["district"]) == ("Raiwind", "Lahore")


async def test_the_farmer_contact_goes_only_to_the_admin_and_the_accepted_transporter(api, world):
    await fund(api, world)
    # the factory and the transporter holding only an offer do not get the farmer phone
    factory_view = (await api.get(f"/api/jobs/{world.job_id}", headers=FACTORY)).json()
    assert factory_view["farmer_phone"] is None
    assert (await api.get(f"/api/jobs/{world.job_id}", headers=ADMIN)).json()["farmer_phone"] == (
        world.farmer_phone
    )
    accepted = await api.post(f"/api/offers/{await offer_id_for(api, T1)}/accept", headers=T1)
    assert accepted.json()["farmer_phone"] == world.farmer_phone
    mine = (await api.get("/api/jobs", headers=T1)).json()
    assert mine[0]["farmer_phone"] == world.farmer_phone
    assert mine[0]["transporter_name"] is not None or mine[0]["transporter_id"]


async def test_a_farmer_reads_the_job_of_their_own_lot_only(api, world):
    me = {"X-Dev-Uid": "f-owner", "X-Dev-Phone": world.farmer_phone}
    await api.post("/api/me/register", headers=me, json={"role": "farmer", "display_name": "Owner"})
    assert [j["id"] for j in (await api.get("/api/jobs", headers=me)).json()] == [world.job_id]
    assert (await api.get(f"/api/jobs/{world.job_id}", headers=me)).status_code == 200
    stranger = {"X-Dev-Uid": "f-other", "X-Dev-Phone": "+923007770123"}
    await api.post(
        "/api/me/register", headers=stranger, json={"role": "farmer", "display_name": "Other"}
    )
    assert (await api.get("/api/jobs", headers=stranger)).json() == []
    assert (await api.get(f"/api/jobs/{world.job_id}", headers=stranger)).status_code == 404
    farmer_view = (await api.get(f"/api/jobs/{world.job_id}", headers=me)).json()
    assert farmer_view["farmer_phone"] is None  # a farmer does not need their own number echoed


# --- decline and the ladder ---------------------------------------------------------------


async def test_declining_sends_the_job_to_the_next_transporter_at_once(api, world):
    await fund(api, world)
    first = await offer_id_for(api, T1)
    assert (await api.post(f"/api/offers/{first}/decline", headers=T1)).status_code == 204
    rows = await offers_of(api, world.job_id)
    assert [(r[2]) for r in rows] == ["expired", "pending"]
    assert rows[1][1] == world.t2_id
    assert (await api.get(f"/api/jobs/{world.job_id}", headers=ADMIN)).json()["state"] == "offered"
    assert (await api.post(f"/api/offers/{first}/decline", headers=T1)).status_code == 409


async def test_when_everyone_declines_the_job_waits_for_a_person(api, world):
    await fund(api, world)
    await api.post(f"/api/offers/{await offer_id_for(api, T1)}/decline", headers=T1)
    await api.post(f"/api/offers/{await offer_id_for(api, T2)}/decline", headers=T2)
    job = (await api.get(f"/api/jobs/{world.job_id}", headers=ADMIN)).json()
    assert (job["state"], job["offers_exhausted"]) == ("funded", True)


async def test_a_transporter_cannot_decline_someone_elses_offer(api, world):
    await fund(api, world)
    mine = await offer_id_for(api, T1)
    assert (await api.post(f"/api/offers/{mine}/decline", headers=T2)).status_code == 404
    assert (await api.post("/api/offers/not-a-uuid/decline", headers=T1)).status_code == 404


async def test_the_admin_sees_the_whole_ladder_for_a_job(api, world):
    await fund(api, world)
    await api.post(f"/api/offers/{await offer_id_for(api, T1)}/decline", headers=T1)
    ladder = (await api.get(f"/api/jobs/{world.job_id}/offers", headers=ADMIN)).json()
    assert [(o["sequence"], o["status"]) for o in ladder] == [(1, "expired"), (2, "pending")]
    assert ladder[0]["transporter_id"] == world.t1_id
    assert ladder[0]["payout_amount"] == TRANSPORTER_ESTIMATE
    assert (await api.get(f"/api/jobs/{world.job_id}/offers", headers=FACTORY)).status_code == 403


async def test_the_transporter_list_names_people(api, world):
    rows = (await api.get("/api/transporters", headers=ADMIN)).json()
    mine = next(t for t in rows if t["id"] == world.t1_id)
    assert mine["user_uid"] == "t-trans1"
    assert "display_name" in mine


# --- stats --------------------------------------------------------------------------------


async def test_stats_summarise_the_platform_for_the_admin(api, world):
    await fund(api, world)
    stats = (await api.get("/api/stats", headers=ADMIN)).json()
    assert stats["live_jobs"] >= 1 and stats["farmers"] >= 1 and stats["factories"] >= 1
    assert stats["escrow_held"] >= GROSS
    assert set(stats) >= {"transporters", "orders", "tonnes_diverted", "open_escalations"}
    assert (await api.get("/api/stats", headers=FACTORY)).status_code == 403


# --- the local dispatch loop --------------------------------------------------------------


async def test_one_loop_tick_advances_an_offer_that_has_lapsed(api, world):
    await fund(api, world)
    await api.session.execute(
        text("UPDATE offers SET expires_at = :t WHERE job_id = :j"),
        {"t": datetime.now(UTC) - timedelta(seconds=5), "j": __import__("uuid").UUID(world.job_id)},
    )
    result = await run_once(api.session, api.inbox)
    assert (result.expired, result.reoffered) == (1, 1)
    assert [r[2] for r in await offers_of(api, world.job_id)] == ["expired", "pending"]
    assert {"offer.expired", "offer.created"} <= set(await event_types(api, world.job_id))


def test_the_loop_is_off_by_default_and_never_on_cloud_run(monkeypatch):
    monkeypatch.delenv("DISPATCH_LOOP_SECONDS", raising=False)
    monkeypatch.delenv("K_SERVICE", raising=False)
    assert loop_seconds() == 0
    monkeypatch.setenv("DISPATCH_LOOP_SECONDS", "2")
    assert loop_seconds() == 2.0
    monkeypatch.setenv("K_SERVICE", "residue-api")
    assert loop_seconds() == 0
    monkeypatch.delenv("K_SERVICE")
    monkeypatch.setenv("DISPATCH_LOOP_SECONDS", "soon")
    assert loop_seconds() == 0
