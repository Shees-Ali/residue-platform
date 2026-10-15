# ruff: noqa: E501
"""The whole story over HTTP, one role after another, on the real routes and the real database
(rolled back at the end): a farmer reports residue and is paid; a buyer buys a product.

farmer reports -> factory funds -> transporter accepts, picks up, delivers -> factory weighs ->
farmer confirms -> settled -> ledger balanced, impact up -> marketplace sale with its split.
"""
from tests.helpers import ADMIN, FACTORY, T1, leg, tomorrow

FARMER = {"X-Dev-Uid": "e2e-farmer", "X-Dev-Phone": "+923008881234"}
BUYER = {"X-Dev-Uid": "e2e-buyer"}
JPEG = {"Content-Type": "image/jpeg"}


async def take_photo(api, job_id, kind, headers=T1):
    """Ask for an upload address, upload a real file to it, return the path."""
    slot = await api.post(
        f"/api/jobs/{job_id}/photos/upload-url", headers=headers, json={"kind": kind}
    )
    assert slot.status_code == 200, slot.text
    put = await api.put(slot.json()["upload_url"], headers={**headers, **JPEG}, content=b"\xff\xd8jpeg")
    assert put.status_code == 204, put.text
    return slot.json()["path"]


async def test_a_lot_goes_from_the_farmer_to_settled_and_the_money_balances(api, world):
    # --- the farmer signs up and reports residue on the web
    me = await api.post(
        "/api/me/register", headers=FARMER, json={"role": "farmer", "display_name": "Fatima Bibi"}
    )
    assert me.status_code == 201 and me.json()["farmer_linked"] is True
    lot = await api.post(
        "/api/lots/mine",
        headers={**FARMER, "Idempotency-Key": "e2e-1"},
        json={
            "residue_type": "rice_straw", "quantity_tonnes": 2.5, "pickup_date": tomorrow(),
            "pickup_part": "morning", "village": "Raiwind", "district": "Lahore",
        },
    )
    assert lot.status_code == 201, lot.text
    job_id = lot.json()["job_id"]
    assert lot.json()["factory_name"] == "Test Factory" and lot.json()["job_state"] == "created"

    before = (await api.get("/api/impact", headers=ADMIN)).json()["tonnes_diverted"]

    # --- the factory funds the escrow; the nearest transporter is offered the load
    funded = await api.post(f"/api/jobs/{job_id}/fund", headers=FACTORY)
    assert funded.status_code == 200 and funded.json()["state"] == "offered"
    escrow = funded.json()["escrow_amount"]
    offers = (await api.get("/api/offers", headers=T1)).json()
    offer = next(o for o in offers if o["job_id"] == job_id and o["status"] == "pending")

    # --- the transporter accepts, shares location, picks up and delivers with photos
    accepted = await api.post(f"/api/offers/{offer['id']}/accept", headers=T1)
    assert accepted.status_code == 200 and accepted.json()["farmer_phone"] == FARMER["X-Dev-Phone"]
    ping = await api.post(f"/api/jobs/{job_id}/location", headers=T1, json={"lat": 31.40, "lon": 74.38})
    assert ping.json() == {"recorded": True}
    picked = await api.post(
        f"/api/jobs/{job_id}/pickup", headers=T1, json=leg(await take_photo(api, job_id, "pickup"), 2450)
    )
    assert picked.status_code == 200 and picked.json()["state"] == "picked_up"
    delivered = await api.post(
        f"/api/jobs/{job_id}/deliver", headers=T1, json=leg(await take_photo(api, job_id, "delivery"), 2440)
    )
    assert delivered.json()["state"] == "delivered"
    assert {p["kind"] for p in delivered.json()["photos"]} == {"pickup", "delivery"}

    # --- the admin and the factory can follow the load
    track = (await api.get(f"/api/jobs/{job_id}/track", headers=FACTORY)).json()
    assert [p["kind"] for p in track["points"]] == ["ping", "pickup", "delivery"]

    # --- the factory weighs it; the farmer is asked to confirm
    weighed = await api.post(
        f"/api/jobs/{job_id}/confirm", headers=FACTORY, json={"accept": True, "final_weight_kg": 2480}
    )
    assert weighed.status_code == 200 and weighed.json()["state"] == "confirmed"
    waiting = (await api.get("/api/jobs?state=confirmed", headers=FARMER)).json()
    assert [j["id"] for j in waiting] == [job_id] and waiting[0]["final_weight_kg"] == 2480
    owed = (await api.get("/api/ledger/mine", headers=FARMER)).json()
    assert owed[0]["status"] == "pending" and owed[0]["amount"] == waiting[0]["est_farmer_payout"]

    # --- the farmer says yes: settled and paid
    paid = await api.post(
        f"/api/jobs/{job_id}/verify", headers=FARMER, json={"confirmed": True, "note": ""}
    )
    assert paid.status_code == 200 and paid.json()["state"] == "settled"
    assert paid.json()["farmer_amount"] == owed[0]["amount"]
    assert (await api.get("/api/ledger/mine", headers=FARMER)).json()[0]["status"] == "released"
    assert (await api.get("/api/ledger/mine", headers=T1)).json()[0]["status"] == "released"

    # --- the money adds up and the impact counter rose by the weighbridge weight
    ledger = (await api.get(f"/api/jobs/{job_id}/ledger", headers=FACTORY)).json()
    by_kind = {e["kind"]: e["amount"] for e in ledger}
    assert by_kind["escrow_in"] >= escrow
    out = sum(a for k, a in by_kind.items() if k != "escrow_in")
    assert out == by_kind["escrow_in"]  # released, fees and refunds equal what went in
    assert (await api.get("/api/ledger/check", headers=ADMIN)).json()["balanced"] is True
    after = (await api.get("/api/impact", headers=ADMIN)).json()["tonnes_diverted"]
    assert round(after - before, 2) == 2.48
    stats = (await api.get("/api/stats", headers=ADMIN)).json()
    assert stats["jobs_settled"] >= 1 and stats["tonnes_diverted"] >= 2.48

    # --- a buyer buys a product; the sale is split four ways and the ledger still balances
    await api.post(
        "/api/me/register", headers=BUYER, json={"role": "buyer", "display_name": "Bilal Ahmed"}
    )
    product = await api.post(
        "/api/products",
        headers=FACTORY,
        json={
            "name": "Biomass pellets", "unit_price": 25_000, "stock": 20, "category": "Clean Energy",
            "unit": "per 25 kg bag", "description": "Dense pellets for boilers.",
        },
    )
    assert product.status_code == 201, product.text
    sale = await api.post(
        "/api/orders", headers=BUYER, json={"product_id": product.json()["id"], "quantity": 4}
    )
    assert sale.status_code == 201 and sale.json()["shares_total_bps"] == 10_000
    assert sale.json()["amounts_total"] == sale.json()["total"] == 100_000
    shelf = (await api.get("/api/products", headers=BUYER)).json()
    assert next(p for p in shelf if p["id"] == product.json()["id"])["stock"] == 16
    assert (await api.get("/api/ledger/check", headers=ADMIN)).json()["balanced"] is True


async def test_a_disputed_lot_freezes_the_money_and_reaches_the_admin(api, world):
    await api.post(
        "/api/me/register", headers=FARMER, json={"role": "farmer", "display_name": "Fatima Bibi"}
    )
    lot = await api.post(
        "/api/lots/mine",
        headers={**FARMER, "Idempotency-Key": "e2e-2"},
        json={
            "residue_type": "rice_straw", "quantity_tonnes": 2, "pickup_date": tomorrow(),
            "pickup_part": "evening", "village": "Raiwind", "district": "Lahore",
        },
    )
    job_id = lot.json()["job_id"]
    await api.post(f"/api/jobs/{job_id}/fund", headers=FACTORY)
    offer = next(
        o for o in (await api.get("/api/offers", headers=T1)).json() if o["job_id"] == job_id
    )
    await api.post(f"/api/offers/{offer['id']}/accept", headers=T1)
    await api.post(
        f"/api/jobs/{job_id}/pickup", headers=T1, json=leg(await take_photo(api, job_id, "pickup"), 1900)
    )
    await api.post(
        f"/api/jobs/{job_id}/deliver", headers=T1, json=leg(await take_photo(api, job_id, "delivery"), 1900)
    )
    await api.post(
        f"/api/jobs/{job_id}/confirm", headers=FACTORY, json={"accept": True, "final_weight_kg": 1200}
    )
    disputed = await api.post(
        f"/api/jobs/{job_id}/verify",
        headers=FARMER,
        json={"confirmed": False, "note": "I loaded 1900 kg, not 1200"},
    )
    assert disputed.json()["state"] == "disputed"
    queue = (await api.get("/api/escalations", headers=ADMIN)).json()
    assert any(e["job_id"] == job_id and e["farmer_phone"] == FARMER["X-Dev-Phone"] for e in queue)
    assert (await api.get("/api/ledger/check", headers=ADMIN)).json()["balanced"] is True
