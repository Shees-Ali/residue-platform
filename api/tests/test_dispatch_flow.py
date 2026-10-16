"""A1 assignment, FA1 funding, A2 offer ladder and T1 accept, through the real routes.

DB-backed (skipped without DATABASE_URL) and rolled back, except the race test, which needs two
real connections and cleans up after itself.
"""
import asyncio
import os
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import HTTPException
from sqlalchemy import text

from tests.helpers import (
    FACTORY,
    GROSS,
    T1,
    T2,
    TRANSPORTER_ESTIMATE,
    event_types,
    fund,
    offers_of,
    scalar,
    tomorrow,
)

# --- A1 assignment ---------------------------------------------------------------------------


async def test_a_new_lot_is_ranked_and_assigned_to_the_best_factory(api, world):
    ranking = (await api.get(f"/api/lots/{world.lot_id}/ranking")).json()
    assert ranking[0]["factory_id"] == world.factory_id
    assert ranking[0]["chosen"] and ranking[0]["rank"] == 1
    assert [e["rank"] for e in ranking] == list(range(1, len(ranking) + 1))
    lots = (await api.get("/api/lots")).json()
    mine = next(lot for lot in lots if lot["id"] == world.lot_id)
    assert (mine["status"], mine["job_state"]) == ("assigned", "created")


async def test_admin_override_needs_a_reason_and_an_eligible_factory_and_is_logged(api, world):
    ranking = (await api.get(f"/api/lots/{world.lot_id}/ranking")).json()
    other = ranking[1]["factory_id"]
    url = f"/api/lots/{world.lot_id}/override"
    assert (await api.post(url, json={"factory_id": other, "reason": "  "})).status_code == 422
    assert (await api.post(url, json={"factory_id": str(uuid.uuid4()), "reason": "x"})
            ).status_code == 422
    ok = await api.post(url, json={"factory_id": other, "reason": "farmer asked for this mill"})
    assert ok.status_code == 200 and ok.json()["factory_id"] == other
    after = (await api.get(f"/api/lots/{world.lot_id}/ranking")).json()
    chosen = [e for e in after if e["chosen"]]
    assert [e["factory_id"] for e in chosen] == [other]
    assert chosen[0]["override_reason"] == "farmer asked for this mill"


async def test_override_after_funding_is_refused(api, world):
    await fund(api, world)
    other = (await api.get(f"/api/lots/{world.lot_id}/ranking")).json()[1]["factory_id"]
    r = await api.post(
        f"/api/lots/{world.lot_id}/override", json={"factory_id": other, "reason": "late"}
    )
    assert r.status_code == 409


async def test_only_admins_see_lots_and_override(api, world):
    assert (await api.get("/api/lots", headers=FACTORY)).status_code == 403
    r = await api.post(
        f"/api/lots/{world.lot_id}/override", headers=T1, json={"factory_id": "x", "reason": "r"}
    )
    assert r.status_code == 403


async def test_admin_can_enter_a_lot_by_hand_and_it_is_assigned_too(api, world):
    r = await api.post(
        "/api/lots",
        json={"farmer_phone": "+923008880002", "residue_type": "rice_straw",
              "quantity_tonnes": 1, "pickup_date": tomorrow(), "pickup_part": "evening",
              "village": "Raiwind", "district": "Lahore"},
    )
    assert r.status_code == 201
    lots = (await api.get("/api/lots")).json()
    row = next(lot for lot in lots if lot["id"] == r.json()["lot_id"])
    assert row["job_state"] == "created"


# --- FA1 funding ------------------------------------------------------------------------------


async def test_an_unfunded_job_has_no_offers(api, world):
    assert await offers_of(api, world.job_id) == []
    assert (await api.get("/api/offers", headers=T1)).json() == []


async def test_funding_writes_escrow_and_offers_the_job_to_the_nearest_transporter(api, world):
    job = await fund(api, world)
    assert job["state"] == "offered" and job["funded_at"]
    escrow = await scalar(
        api, "SELECT sum(amount) FROM ledger_entries WHERE job_id = :j AND kind = 'escrow_in'",
        j=uuid.UUID(world.job_id))
    assert escrow == GROSS
    assert await offers_of(api, world.job_id) == [
        (1, world.t1_id, "pending", TRANSPORTER_ESTIMATE)
    ]
    mine = (await api.get("/api/offers", headers=T1)).json()
    assert [(o["status"], o["payout_amount"], o["factory_name"]) for o in mine] == [
        ("pending", TRANSPORTER_ESTIMATE, "Test Factory")
    ]
    assert (await api.get("/api/offers", headers=T2)).json() == []
    assert {"job.funded", "offer.created"} <= set(await event_types(api, world.job_id))


async def test_only_the_owning_factory_can_fund_and_only_once(api, world):
    url = f"/api/jobs/{world.job_id}/fund"
    assert (await api.post(url, headers={"X-Dev-Uid": "dev-factory-0"})).status_code == 404
    assert (await api.post(url, headers=T1)).status_code == 403
    assert (await api.post(url)).status_code == 403  # admin is not a factory
    await fund(api, world)
    assert (await api.post(url, headers=FACTORY)).status_code == 409


async def test_jobs_are_scoped_by_role(api, world):
    assert world.job_id in [j["id"] for j in (await api.get("/api/jobs")).json()]
    assert world.job_id in [j["id"] for j in (await api.get("/api/jobs", headers=FACTORY)).json()]
    assert (await api.get("/api/jobs", headers=T1)).json() == []  # nothing assigned yet
    other = await api.get(f"/api/jobs/{world.job_id}", headers={"X-Dev-Uid": "dev-factory-0"})
    assert other.status_code == 404


# --- T1 accept and A2 ladder ---------------------------------------------------------------


async def first_offer_id(api, world):
    return await scalar(
        api, "SELECT id FROM offers WHERE job_id = :j AND sequence = 1", j=uuid.UUID(world.job_id))


async def test_accept_assigns_the_transporter_and_a_second_accept_loses(api, world):
    await fund(api, world)
    offer = await first_offer_id(api, world)
    assert (await api.post(f"/api/offers/{offer}/accept", headers=T2)).status_code == 404
    won = await api.post(f"/api/offers/{offer}/accept", headers=T1)
    assert won.status_code == 200
    assert (won.json()["state"], won.json()["transporter_id"]) == ("accepted", world.t1_id)
    lost = await api.post(f"/api/offers/{offer}/accept", headers=T1)
    assert lost.status_code == 409
    assert (await api.get(f"/api/jobs/{world.job_id}", headers=T1)).status_code == 200
    assert (await api.get(f"/api/jobs/{world.job_id}", headers=T2)).status_code == 404


async def test_an_expired_offer_cannot_be_accepted(api, world):
    await fund(api, world)
    offer = await first_offer_id(api, world)
    await api.session.execute(
        text("UPDATE offers SET expires_at = now() - interval '1 minute' WHERE id = :o"),
        {"o": offer})
    assert (await api.post(f"/api/offers/{offer}/accept", headers=T1)).status_code == 409


async def test_tick_moves_an_unanswered_offer_to_the_next_transporter_then_exhausts(api, world):
    await fund(api, world)
    past = "UPDATE offers SET expires_at = now() - interval '1 minute' WHERE status = 'pending'"
    nothing = await api.post("/api/dispatch/tick")
    assert nothing.json() == {"expired": 0, "reoffered": 0, "exhausted": 0, "dispatched": 0}

    await api.session.execute(text(past))
    first = await api.post("/api/dispatch/tick")
    assert first.json() == {"expired": 1, "reoffered": 1, "exhausted": 0, "dispatched": 0}
    assert [(o[0], o[1], o[2]) for o in await offers_of(api, world.job_id)] == [
        (1, world.t1_id, "expired"), (2, world.t2_id, "pending")]

    await api.session.execute(text(past))
    last = await api.post("/api/dispatch/tick")
    assert last.json() == {"expired": 1, "reoffered": 0, "exhausted": 1, "dispatched": 0}
    job = (await api.get(f"/api/jobs/{world.job_id}")).json()
    assert (job["state"], job["offers_exhausted"]) == ("funded", True)


async def test_force_tick_is_the_admin_demo_fast_forward(api, world):
    await fund(api, world)
    assert (await api.post("/api/dispatch/tick", headers=FACTORY, json={"force": True})
            ).status_code == 403
    forced = await api.post("/api/dispatch/tick", json={"force": True})
    assert forced.json() == {"expired": 1, "reoffered": 1, "exhausted": 0, "dispatched": 0}


# --- T1 race: two real connections ------------------------------------------------------------


@pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="DATABASE_URL not set")
async def test_two_simultaneous_accepts_produce_exactly_one_winner():
    from sqlalchemy import delete
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from sqlalchemy.pool import NullPool

    from app.config import get_settings
    from app.db import async_url
    from app.db_models import tables as t
    from app.services.dispatch_store import accept_offer

    engine = create_async_engine(async_url(get_settings().database_url), poolclass=NullPool)
    Session = async_sessionmaker(engine, expire_on_commit=False)  # noqa: N806
    tag = uuid.uuid4().hex[:8]
    async with Session() as s:
        factory = t.Factory(name=f"race-{tag}", lat=0, lon=0, price_per_tonne=1)
        farmer = t.Farmer(phone=f"+9299{int(tag, 16) % 10**8:08d}")
        transporter = t.Transporter(phone=f"+9288{int(tag, 16) % 10**8:08d}", lat=0, lon=0)
        s.add_all([factory, farmer, transporter])
        await s.flush()
        lot = t.Lot(farmer_id=farmer.id, residue_code="rice_straw", quantity_tonnes=1, lat=0, lon=0)
        s.add(lot)
        await s.flush()
        job = t.Job(lot_id=lot.id, factory_id=factory.id, state="offered",
                    quoted_price_per_tonne=1, farmer_share_bps=7000, est_weight_kg=1000)
        s.add(job)
        await s.flush()
        offer = t.Offer(job_id=job.id, transporter_id=transporter.id, sequence=1,
                        expires_at=datetime.now(UTC) + timedelta(minutes=5), payout_amount=1)
        s.add(offer)
        await s.commit()
        ids = (offer.id, transporter.id, job.id, lot.id, farmer.id, factory.id)

    async def attempt():
        async with Session() as s:
            who = await s.get(t.Transporter, ids[1])
            try:
                await accept_offer(s, ids[0], who)
                await s.commit()
                return "won"
            except HTTPException as e:
                await s.rollback()
                return e.status_code

    try:
        results = await asyncio.gather(attempt(), attempt())
        assert sorted(results, key=str) == [409, "won"]
        async with Session() as s:
            assert (await s.get(t.Job, ids[2])).state == "accepted"
    finally:
        async with Session() as s:
            await s.execute(delete(t.Notification).where(t.Notification.job_id == ids[2]))
            await s.execute(delete(t.Event).where(t.Event.job_id == ids[2]))
            for model, key in ((t.Offer, ids[0]), (t.Job, ids[2]), (t.Lot, ids[3]),
                               (t.Transporter, ids[1]), (t.Farmer, ids[4]), (t.Factory, ids[5])):
                await s.execute(delete(model).where(model.id == key))
            await s.commit()
        await engine.dispose()
