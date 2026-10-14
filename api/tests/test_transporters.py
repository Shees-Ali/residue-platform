"""A2: admins approve transporters; the tier sets job size; waiting jobs go out on the tick."""
import uuid

from sqlalchemy import text

from tests.helpers import ADMIN, FACTORY, T1, fund, offers_of, scalar, tomorrow


async def approve(api, transporter_id, tier, headers=ADMIN):
    return await api.post(
        f"/api/transporters/{transporter_id}/approve", headers=headers, json={"tier": tier}
    )


async def big_lot(api, world, tonnes=4):
    """A lot bigger than a tier 1 transporter may carry, assigned to the test factory."""
    r = await api.post("/api/lots", json={
        "farmer_phone": "+923008880005", "residue_type": "rice_straw", "quantity_tonnes": tonnes,
        "pickup_date": tomorrow(), "pickup_part": "morning", "village": "Raiwind",
        "district": "Lahore"})
    assert r.status_code == 201, r.text
    lot = uuid.UUID(r.json()["lot_id"])
    return str(await scalar(api, "SELECT id FROM jobs WHERE lot_id = :l", l=lot))


async def test_approving_sets_the_tier_and_the_largest_job(api, world):
    await api.session.execute(text("UPDATE transporters SET approved_at = NULL, tier = 1"))
    r = await approve(api, world.t1_id, 2)
    assert r.status_code == 200
    assert (r.json()["approved"], r.json()["tier"], r.json()["max_tonnes"]) == (True, 2, 7.0)
    retier = await approve(api, world.t1_id, 3)
    assert (retier.json()["tier"], retier.json()["max_tonnes"]) == (3, 15.0)
    ids = [t["id"] for t in (await api.get("/api/transporters?approved=true")).json()]
    assert ids == [world.t1_id]
    waiting = [t["id"] for t in (await api.get("/api/transporters?approved=false")).json()]
    assert world.t1_id not in waiting and world.t2_id in waiting


async def test_revoking_stops_offers_and_only_admins_manage_transporters(api, world):
    assert (await approve(api, world.t1_id, 1, headers=FACTORY)).status_code == 403
    assert (await approve(api, world.t1_id, 1, headers=T1)).status_code == 403
    assert (await approve(api, world.t1_id, 9)).status_code == 422
    assert (await approve(api, str(uuid.uuid4()), 1)).status_code == 404
    assert (await approve(api, "nope", 1)).status_code == 404
    assert (await api.get("/api/transporters", headers=FACTORY)).status_code == 403
    revoked = await api.post(f"/api/transporters/{world.t1_id}/revoke")
    assert revoked.json()["approved"] is False
    await fund(api, world)  # t1 is no longer eligible, so the first offer goes to t2
    assert [o[1] for o in await offers_of(api, world.job_id)] == [world.t2_id]


async def test_the_tier_limits_which_jobs_a_transporter_is_offered(api, world):
    await approve(api, world.t1_id, 1)  # 3 t
    await approve(api, world.t2_id, 1)
    job_id = await big_lot(api, world, tonnes=4)
    funded = await api.post(f"/api/jobs/{job_id}/fund", headers=FACTORY)
    assert funded.json()["state"] == "funded"  # nobody can carry 4 t yet
    assert await offers_of(api, job_id) == []


async def test_the_tick_sends_a_waiting_job_once_someone_can_carry_it(api, world):
    await approve(api, world.t1_id, 1)
    await approve(api, world.t2_id, 1)
    job_id = await big_lot(api, world, tonnes=4)
    await api.post(f"/api/jobs/{job_id}/fund", headers=FACTORY)
    idle = (await api.post("/api/dispatch/tick")).json()
    assert idle["dispatched"] == 0
    await approve(api, world.t1_id, 3)  # 15 t
    sent = (await api.post("/api/dispatch/tick")).json()
    assert sent == {"expired": 0, "reoffered": 0, "exhausted": 0, "dispatched": 1}
    assert [(o[0], o[1], o[2]) for o in await offers_of(api, job_id)] == [
        (1, world.t1_id, "pending")]
    again = (await api.post("/api/dispatch/tick")).json()
    assert again["dispatched"] == 0  # it already has an offer


async def test_an_admin_can_redispatch_after_every_transporter_passed(api, world):
    await fund(api, world)
    past = "UPDATE offers SET expires_at = now() - interval '1 minute' WHERE status = 'pending'"
    for _ in range(2):  # t1 and t2 both let their offers lapse
        await api.session.execute(text(past))
        await api.post("/api/dispatch/tick")
    job = (await api.get(f"/api/jobs/{world.job_id}")).json()
    assert (job["state"], job["offers_exhausted"]) == ("funded", True)
    url = f"/api/jobs/{world.job_id}/redispatch"
    assert (await api.post(url)).status_code == 409  # everyone eligible was already asked

    newcomer = await scalar(api, "SELECT id FROM transporters WHERE id NOT IN (:a, :b) LIMIT 1",
                            a=uuid.UUID(world.t1_id), b=uuid.UUID(world.t2_id))
    await approve(api, str(newcomer), 3)
    assert (await api.post(url, headers=FACTORY)).status_code == 403
    r = await api.post(url)
    assert r.status_code == 200 and r.json()["state"] == "offered"
    assert (await offers_of(api, world.job_id))[-1][:3] == (3, str(newcomer), "pending")
    assert (await api.post(url)).status_code == 409  # it is offered again, not waiting


async def test_redispatch_only_applies_to_a_funded_job(api, world):
    assert (await api.post(f"/api/jobs/{world.job_id}/redispatch")).status_code == 409  # created
    await fund(api, world)
    assert (await api.post(f"/api/jobs/{world.job_id}/redispatch")).status_code == 409  # offered
    assert (await api.post(f"/api/jobs/{uuid.uuid4()}/redispatch")).status_code == 404
