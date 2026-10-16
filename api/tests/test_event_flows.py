# ruff: noqa: E501
"""EV1/EV2 beyond the happy path: unmatched lots, the offer ladder, accounts, orders, edits,
escalations, the ledger alert, and the rule that a refused action leaves no event behind."""
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import text

from tests.helpers import (
    ADMIN,
    FACTORY,
    OTHER_FACTORY,
    T1,
    T2,
    event_types,
    fund,
    leg,
    scalar,
    tomorrow,
)

BUYER = {"X-Dev-Uid": "flow-buyer"}


async def bell(api, headers) -> list[dict]:
    return (await api.get("/api/notifications?limit=50", headers=headers)).json()["items"]


async def last(api, headers) -> dict:
    return (await api.get("/api/notifications?limit=1", headers=headers)).json()["items"][0]


async def lapse(api, job_id):
    await api.session.execute(
        text("UPDATE offers SET expires_at = :t WHERE job_id = :j AND status = 'pending'"),
        {"t": datetime.now(UTC) - timedelta(seconds=5), "j": uuid.UUID(job_id)},
    )


# --- lots -----------------------------------------------------------------------------------


async def test_a_lot_no_factory_buys_is_reported_to_the_farmer_and_the_admin(api, world):
    await api.session.execute(text("DELETE FROM factory_residues WHERE residue_code = 'cotton_stalk'"))
    r = await api.post(
        "/api/lots", headers=ADMIN,
        json={"farmer_phone": "+923009991111", "residue_type": "cotton_stalk", "quantity_tonnes": 2,
              "pickup_date": tomorrow(), "pickup_part": "morning", "village": "Raiwind", "district": "Lahore"},
    )
    assert r.status_code == 201, r.text
    assert "lot.unmatched" in await event_types(api)
    admin_msg = (await last(api, ADMIN))
    assert admin_msg["type"] == "lot.unmatched" and "matches no factory" in admin_msg["body"]
    # the farmer has no login (they phoned): the message waits on the farmer record, not on a uid
    waiting = await scalar(
        api,
        "SELECT count(*) FROM notifications WHERE type = 'lot.unmatched' AND recipient_uid IS NULL AND recipient_farmer_id IS NOT NULL",
    )
    assert waiting == 1


async def test_an_admin_edit_tells_the_factory_and_a_manual_move_tells_both_factories(api, world):
    edit = await api.patch(f"/api/lots/{world.lot_id}", headers=ADMIN, json={"quantity_tonnes": 3})
    assert edit.status_code == 200, edit.text
    msg = await last(api, FACTORY)
    assert msg["type"] == "lot.updated" and "3 t" in msg["body"]

    ranking = (await api.get(f"/api/lots/{world.lot_id}/ranking", headers=ADMIN)).json()
    other = next(e for e in ranking if not e["chosen"])
    moved = await api.post(
        f"/api/lots/{world.lot_id}/override", headers=ADMIN,
        json={"factory_id": other["factory_id"], "reason": "Closer to the road"},
    )
    assert moved.status_code == 200, moved.text
    assert (await last(api, FACTORY))["type"] == "lot.reassigned"
    assert (await last(api, FACTORY))["title"] == "Lot withdrawn"  # the old factory
    new_owner = await scalar(api, "SELECT user_uid FROM factories WHERE id = :f", f=uuid.UUID(other["factory_id"]))
    if new_owner:
        assert (await last(api, {"X-Dev-Uid": new_owner}))["title"] == "New lot for you"


# --- dispatch -------------------------------------------------------------------------------


async def test_an_offer_that_runs_out_moves_on_and_a_spent_ladder_alerts_the_admin_and_factory(api, world):
    await fund(api, world)
    first = await last(api, T1)
    assert first["type"] == "offer.created" and "Answer within" in first["body"] and "PKR" in first["body"]
    await lapse(api, world.job_id)
    assert (await api.post("/api/dispatch/tick", headers=ADMIN)).status_code == 200
    assert [n["type"] for n in await bell(api, T1)][:2] == ["offer.expired", "offer.created"]
    assert (await last(api, T2))["type"] == "offer.created"  # the next nearest transporter
    await lapse(api, world.job_id)
    assert (await api.post("/api/dispatch/tick", headers=ADMIN)).status_code == 200
    assert (await last(api, ADMIN))["type"] == "job.offers_exhausted" and (await last(api, ADMIN))["level"] == "warning"
    assert (await last(api, FACTORY))["type"] == "job.offers_exhausted"


async def test_declining_tells_the_admin_and_offers_the_next_transporter(api, world):
    await fund(api, world)
    offer = (await api.get("/api/offers", headers=T1)).json()[0]
    assert (await api.post(f"/api/offers/{offer['id']}/decline", headers=T1)).status_code == 204
    assert "offer.declined" in [n["type"] for n in await bell(api, ADMIN)]
    assert (await last(api, T2))["type"] == "offer.created"
    assert (await bell(api, T1))[0]["type"] == "offer.created"  # the decliner is not told about their own act


# --- accounts -------------------------------------------------------------------------------


async def test_account_changes_reach_the_person_and_new_signups_reach_the_admin(api, world):
    me = {"X-Dev-Uid": "flow-truck"}
    r = await api.post("/api/me/register", headers=me, json={
        "role": "transporter", "display_name": "Truck Co", "phone": "+923009990002",
        "village": "Raiwind", "district": "Lahore"})
    assert r.status_code == 201, r.text
    waiting = await last(api, ADMIN)
    assert waiting["type"] == "account.pending" and waiting["title"] == "New transporter waiting"
    assert "users" in waiting["refresh"]  # the approvals table is a users query

    assert (await api.post("/api/users/flow-truck/approve", headers=ADMIN, json={"tier": 2})).status_code == 200
    approved = (await bell(api, me))[0]
    assert approved["type"] == "account.approved" and "me" in approved["refresh"]

    tier = await api.patch("/api/users/flow-truck/profile", headers=ADMIN, json={"transporter": {"tier": 3}})
    assert tier.status_code == 200, tier.text
    changed = await last(api, me)
    assert changed["type"] == "account.tier_changed" and "tier 3" in changed["body"] and "15 t" in changed["body"]

    assert (await api.patch("/api/users/flow-truck/profile", headers=ADMIN, json={"display_name": "Truck Company"})).status_code == 200
    assert (await last(api, me))["type"] == "account.edited"

    assert (await api.post("/api/users/flow-truck/suspend", headers=ADMIN)).status_code == 200
    # a suspended account cannot read its bell (blocked everywhere): reactivate, then it sees both
    assert (await api.post("/api/users/flow-truck/reactivate", headers=ADMIN)).status_code == 200
    types = [n["type"] for n in await bell(api, me)]
    assert types[:2] == ["account.reactivated", "account.suspended"]
    suspended = next(n for n in await bell(api, me) if n["type"] == "account.suspended")
    assert suspended["level"] == "warning"


async def test_a_rejected_signup_is_told_so(api, world):
    me = {"X-Dev-Uid": "flow-nope"}
    await api.post("/api/me/register", headers=me, json={
        "role": "factory", "display_name": "Nope Mill", "village": "Raiwind", "district": "Lahore",
        "factory": {"name": "Nope Mill", "price_per_tonne": 4_000_000, "residues": ["rice_straw"]}})
    assert (await api.post("/api/users/flow-nope/reject", headers=ADMIN)).status_code == 200
    assert await scalar(api, "SELECT type FROM notifications WHERE recipient_uid = 'flow-nope' ORDER BY created_at DESC LIMIT 1") == "account.rejected"


# --- the marketplace ------------------------------------------------------------------------


async def test_an_order_tells_the_factory_and_the_buyer_and_low_stock_warns_once(api, world):
    await api.post("/api/me/register", headers=BUYER, json={"role": "buyer", "display_name": "Bilal Ahmed"})
    product = (await api.post("/api/products", headers=FACTORY, json={
        "name": "Biomass pellets", "unit_price": 25_000, "stock": 7, "category": "Clean Energy",
        "unit": "per 25 kg bag", "description": "Dense pellets."})).json()
    order = await api.post("/api/orders", headers=BUYER, json={"product_id": product["id"], "quantity": 3})
    assert order.status_code == 201, order.text
    receipt = await last(api, BUYER)
    assert receipt["type"] == "order.placed" and "3 x Biomass pellets" in receipt["body"] and "PKR 750" in receipt["body"]
    types = [n["type"] for n in await bell(api, FACTORY)]
    assert types[:2] == ["product.low_stock", "order.placed"]
    assert "down to 4" in (await last(api, FACTORY))["body"]
    assert "product.low_stock" in [n["type"] for n in await bell(api, ADMIN)]
    # a second order that stays below the line does not warn again
    await api.post("/api/orders", headers=BUYER, json={"product_id": product["id"], "quantity": 1})
    assert [n["type"] for n in await bell(api, FACTORY)].count("product.low_stock") == 1
    assert [n["type"] for n in await bell(api, BUYER)] == ["order.placed", "order.placed"]


# --- escalations and the ledger -------------------------------------------------------------


async def test_a_phone_escalation_alerts_the_admin_once_even_if_replayed(api, world):
    body = {"call_id": world.call_id, "summary": "Farmer is upset about the price"}
    first = await api.post("/api/agent/escalations", headers={"Idempotency-Key": "ev-esc"}, json=body)
    again = await api.post("/api/agent/escalations", headers={"Idempotency-Key": "ev-esc"}, json=body)
    assert first.status_code == 201 and again.json() == first.json()
    assert (await event_types(api)).count("escalation.created") == 1
    msg = await last(api, ADMIN)
    assert msg["type"] == "escalation.created" and msg["level"] == "warning"
    assert "upset" not in msg["body"]  # what the farmer said stays in the queue, not in a notification


async def test_an_unbalanced_ledger_alerts_the_admins_but_only_once_per_window(api, world):
    await fund(api, world)
    # a finished job whose money does not add up: escrow went in and nothing came out
    await api.session.execute(text("UPDATE jobs SET state = 'settled' WHERE id = :j"), {"j": uuid.UUID(world.job_id)})
    assert (await api.get("/api/ledger/check", headers=ADMIN)).json()["balanced"] is False
    for _ in range(2):
        assert (await api.post("/api/dispatch/tick", headers=ADMIN)).status_code == 200
    assert (await event_types(api)).count("ledger.unbalanced") == 1
    alert = await last(api, ADMIN)
    assert alert["type"] == "ledger.unbalanced" and alert["level"] == "warning" and "ledger" in alert["refresh"]


# --- nothing is left behind by a refused action ------------------------------------------------


async def test_a_refused_step_leaves_no_event_and_no_notification(api, world):
    await fund(api, world)
    offer = (await api.get("/api/offers", headers=T1)).json()[0]
    await api.post(f"/api/offers/{offer['id']}/accept", headers=T1)
    before = (await event_types(api, world.job_id), await scalar(api, "SELECT count(*) FROM notifications WHERE created_at >= now()"))
    slot = await api.post(f"/api/jobs/{world.job_id}/photos/upload-url", headers=T1, json={"kind": "pickup"})
    await api.put(slot.json()["upload_url"], headers={**T1, "Content-Type": "image/jpeg"}, content=b"\xff\xd8jpeg")
    bad = await api.post(f"/api/jobs/{world.job_id}/pickup", headers=T1, json=leg(slot.json()["path"], 0))
    assert bad.status_code == 422
    assert (await event_types(api, world.job_id), await scalar(api, "SELECT count(*) FROM notifications WHERE created_at >= now()")) == before


async def test_a_funded_lot_edit_is_refused_without_an_event_and_a_bad_district_leaves_nothing(api, world):
    await fund(api, world)
    count = len(await event_types(api))
    assert (await api.patch(f"/api/lots/{world.lot_id}", headers=ADMIN, json={"quantity_tonnes": 3})).status_code == 409
    assert (await api.patch(f"/api/lots/{world.lot_id}", headers=ADMIN, json={"district": "Narnia"})).status_code in (409, 422)
    assert len(await event_types(api)) == count
    farmer = {"X-Dev-Uid": "flow-farmer", "X-Dev-Phone": "+923008887777"}
    await api.post("/api/me/register", headers=farmer, json={"role": "farmer", "display_name": "Asma Bibi"})
    refused = await api.post("/api/lots/mine", headers={**farmer, "Idempotency-Key": "ev-bad"}, json={
        "residue_type": "rice_straw", "quantity_tonnes": 2, "pickup_date": tomorrow(),
        "pickup_part": "morning", "village": "Raiwind", "district": "Narnia"})
    assert refused.status_code == 422
    assert len(await event_types(api)) == count  # no lot.created for a lot that was refused


async def test_the_actor_is_not_told_about_their_own_action(api, world):
    await fund(api, world)  # the factory funded it
    assert "job.funded" not in [n["type"] for n in await bell(api, FACTORY)]
    assert "job.funded" in [n["type"] for n in await bell(api, ADMIN)]
    assert "job.funded" not in [n["type"] for n in await bell(api, OTHER_FACTORY)]
