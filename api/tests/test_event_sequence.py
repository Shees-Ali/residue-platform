# ruff: noqa: E501
"""EV2 and EV1 end to end: the whole story over HTTP, asserting what each person's bell and each
job timeline holds after every step. Rolled back at the end."""
import re

from tests.helpers import ADMIN, FACTORY, T1, T2, leg, tomorrow

FARMER = {"X-Dev-Uid": "seq-farmer", "X-Dev-Phone": "+923008885678"}
JPEG = {"Content-Type": "image/jpeg"}
PEOPLE = {"farmer": FARMER, "factory": FACTORY, "transporter": T1, "admin": ADMIN}


async def bell(api, headers) -> list[str]:
    """Types of a person's notifications, oldest first."""
    page = (await api.get("/api/notifications?limit=50", headers=headers)).json()
    return [n["type"] for n in reversed(page["items"])]


async def everyone(api) -> dict[str, list[str]]:
    return {who: await bell(api, h) for who, h in PEOPLE.items()}


async def upload(api, job_id, kind):
    slot = await api.post(f"/api/jobs/{job_id}/photos/upload-url", headers=T1, json={"kind": kind})
    put = await api.put(slot.json()["upload_url"], headers={**T1, **JPEG}, content=b"\xff\xd8jpeg")
    assert put.status_code == 204
    return slot.json()["path"]


async def register(api):
    r = await api.post("/api/me/register", headers=FARMER, json={"role": "farmer", "display_name": "Fatima Bibi"})
    assert r.status_code == 201, r.text


async def start(api):
    """Report a lot as the (already registered) farmer and return its job id."""
    if (await api.get("/api/me", headers=FARMER)).status_code == 404:
        await register(api)
    lot = await api.post(
        "/api/lots/mine", headers={**FARMER, "Idempotency-Key": "seq-1"},
        json={"residue_type": "rice_straw", "quantity_tonnes": 2.5, "pickup_date": tomorrow(),
              "pickup_part": "morning", "village": "Raiwind", "district": "Lahore"},
    )
    assert lot.status_code == 201, lot.text
    return lot.json()["job_id"]


async def test_each_person_hears_exactly_what_the_catalog_says_at_every_step(api, world):
    await register(api)
    before = await everyone(api)  # the admin may already hold older, unrelated messages

    # 1. the farmer reports a lot: they hear it was matched; the factory is asked to fund; the admin sees it arrive
    job_id = await start(api)
    now = await everyone(api)
    assert now["farmer"] == ["lot.matched"]
    assert now["factory"] == before["factory"] + ["lot.matched"]
    assert now["admin"] == before["admin"] + ["lot.created"]
    assert now["transporter"] == before["transporter"]  # nothing for a transporter yet

    # 2. the factory funds: the farmer and admin hear it, the nearest transporter gets the offer
    assert (await api.post(f"/api/jobs/{job_id}/fund", headers=FACTORY)).status_code == 200
    funded = await everyone(api)
    assert funded["farmer"] == ["lot.matched", "job.funded"]
    assert funded["admin"][-1:] == ["job.funded"]
    assert funded["transporter"] == before["transporter"] + ["offer.created"]
    assert funded["factory"] == now["factory"]  # they did it themselves

    # 3. the transporter accepts: farmer, factory and admin hear it
    offer = next(o for o in (await api.get("/api/offers", headers=T1)).json() if o["job_id"] == job_id)
    assert (await api.post(f"/api/offers/{offer['id']}/accept", headers=T1)).status_code == 200
    accepted = await everyone(api)
    assert accepted["farmer"][-1] == accepted["factory"][-1] == accepted["admin"][-1] == "job.accepted"
    assert accepted["transporter"] == funded["transporter"]

    # 4. pickup and 5. delivery
    pickup = await api.post(f"/api/jobs/{job_id}/pickup", headers=T1, json=leg(await upload(api, job_id, "pickup"), 2450))
    assert pickup.status_code == 200, pickup.text
    deliver = await api.post(f"/api/jobs/{job_id}/deliver", headers=T1, json=leg(await upload(api, job_id, "delivery"), 2440))
    assert deliver.status_code == 200, deliver.text
    moved = await everyone(api)
    assert moved["farmer"][-2:] == ["job.picked_up", "job.delivered"]
    assert moved["factory"][-2:] == ["job.picked_up", "job.delivered"]
    assert {"job.picked_up", "job.delivered"} <= set(moved["admin"][-3:])

    # 6. the factory weighs: the farmer is asked to confirm, the transporter hears their payout
    weighed = await api.post(f"/api/jobs/{job_id}/confirm", headers=FACTORY, json={"accept": True, "final_weight_kg": 2480})
    assert weighed.status_code == 200, weighed.text
    confirmed = await everyone(api)
    assert confirmed["farmer"][-1] == "job.confirmed"
    assert confirmed["transporter"][-1] == "job.confirmed"
    assert confirmed["factory"] == moved["factory"]  # the factory did it
    farmer_bell = (await api.get("/api/notifications?limit=1", headers=FARMER)).json()["items"][0]
    assert "Confirm your payment" == farmer_bell["title"] and "2,480 kg" in farmer_bell["body"]
    assert farmer_bell["job_id"] == job_id and "payouts" in farmer_bell["refresh"]

    # 7. the farmer says yes: they are told they are paid (money results reach the person who acted), the others hear it too
    paid = await api.post(f"/api/jobs/{job_id}/verify", headers=FARMER, json={"confirmed": True, "note": ""})
    assert paid.status_code == 200, paid.text
    done = await everyone(api)
    assert done["farmer"][-1] == done["factory"][-1] == done["admin"][-1] == "job.settled"
    assert done["transporter"] == confirmed["transporter"]  # paid at the weighbridge, nothing new

    # the job timeline: the admin sees every fact, in order, with who did it
    timeline = (await api.get(f"/api/jobs/{job_id}/events", headers=ADMIN)).json()
    types = [e["type"] for e in timeline]
    order = ["lot.created", "lot.matched", "job.funded", "offer.created", "job.accepted", "job.picked_up",
             "job.delivered", "job.confirmed", "job.settled"]
    assert [t for t in types if t in order] == order
    assert next(e for e in timeline if e["type"] == "job.accepted")["actor_role"] == "transporter"
    assert next(e for e in timeline if e["type"] == "job.confirmed")["actor_role"] == "factory"
    assert [e["created_at"] for e in timeline] == sorted(e["created_at"] for e in timeline)

    # each party sees only what is theirs to see
    farmer_types = [e["type"] for e in (await api.get(f"/api/jobs/{job_id}/events", headers=FARMER)).json()]
    assert "offer.created" not in farmer_types and "job.settled" in farmer_types
    carrier_types = [e["type"] for e in (await api.get(f"/api/jobs/{job_id}/events", headers=T1)).json()]
    assert "lot.created" not in carrier_types and "job.accepted" in carrier_types and "job.confirmed" in carrier_types
    factory_types = [e["type"] for e in (await api.get(f"/api/jobs/{job_id}/events", headers=FACTORY)).json()]
    assert "offer.created" in factory_types

    # no timeline line and no notification carries a phone number or an email
    everything = [e["summary"] for e in timeline]
    for headers in PEOPLE.values():
        page = (await api.get("/api/notifications?limit=50", headers=headers)).json()
        everything += [n["title"] + " " + n["body"] for n in page["items"]]
    assert not [t for t in everything if re.search(r"\+?\d[\d\s\-]{8,}\d|\S+@\S+", t)]

    # someone with no part in this job cannot read its events
    assert (await api.get(f"/api/jobs/{job_id}/events", headers=T2)).status_code == 404
    assert (await api.get(f"/api/jobs/{job_id}/events", headers={"X-Dev-Uid": "dev-buyer-0"})).status_code == 403


async def test_a_rejected_load_tells_everyone_and_a_dispute_tells_the_admin(api, world):
    job_id = await start(api)
    await api.post(f"/api/jobs/{job_id}/fund", headers=FACTORY)
    offer = next(o for o in (await api.get("/api/offers", headers=T1)).json() if o["job_id"] == job_id)
    await api.post(f"/api/offers/{offer['id']}/accept", headers=T1)
    await api.post(f"/api/jobs/{job_id}/pickup", headers=T1, json=leg(await upload(api, job_id, "pickup"), 2450))
    await api.post(f"/api/jobs/{job_id}/deliver", headers=T1, json=leg(await upload(api, job_id, "delivery"), 2440))
    rejected = await api.post(f"/api/jobs/{job_id}/confirm", headers=FACTORY, json={"accept": False, "reason": "Too wet to burn"})
    assert rejected.status_code == 200, rejected.text
    state = await everyone(api)
    assert state["farmer"][-1] == "job.rejected" and state["transporter"][-1] == "job.rejected"
    assert state["admin"][-1] == "job.rejected"
    warning = (await api.get("/api/notifications?limit=1", headers=ADMIN)).json()["items"][0]
    assert warning["level"] == "warning"
    # the reason the factory typed is free text: it must not appear anywhere in a notification
    assert "wet" not in " ".join(n["body"] for n in (await api.get("/api/notifications?limit=50", headers=FARMER)).json()["items"])


async def test_a_dispute_reaches_the_admin_the_factory_and_the_farmer(api, world):
    job_id = await start(api)
    await api.post(f"/api/jobs/{job_id}/fund", headers=FACTORY)
    offer = next(o for o in (await api.get("/api/offers", headers=T1)).json() if o["job_id"] == job_id)
    await api.post(f"/api/offers/{offer['id']}/accept", headers=T1)
    await api.post(f"/api/jobs/{job_id}/pickup", headers=T1, json=leg(await upload(api, job_id, "pickup"), 2450))
    await api.post(f"/api/jobs/{job_id}/deliver", headers=T1, json=leg(await upload(api, job_id, "delivery"), 2440))
    await api.post(f"/api/jobs/{job_id}/confirm", headers=FACTORY, json={"accept": True, "final_weight_kg": 1200})
    disputed = await api.post(f"/api/jobs/{job_id}/verify", headers=FARMER, json={"confirmed": False, "note": "That is far too low"})
    assert disputed.status_code == 200, disputed.text
    after = await everyone(api)
    assert after["admin"][-1] == after["factory"][-1] == after["farmer"][-1] == "job.disputed"
    assert (await api.get("/api/notifications?limit=1", headers=ADMIN)).json()["items"][0]["level"] == "warning"
    assert "escalations" in (await api.get("/api/notifications?limit=1", headers=ADMIN)).json()["items"][0]["refresh"]
    assert "too low" not in " ".join(n["body"] for n in (await api.get("/api/notifications?limit=50", headers=ADMIN)).json()["items"])
    # resolving the dispute tells the farmer it was looked at
    queue = (await api.get("/api/escalations", headers=ADMIN)).json()
    mine = next(e for e in queue if e["job_id"] == job_id)
    assert (await api.post(f"/api/escalations/{mine['id']}/resolve", headers=ADMIN)).status_code == 204
    assert (await bell(api, FARMER))[-1] == "escalation.resolved"
