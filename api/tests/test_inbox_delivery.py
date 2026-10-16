# ruff: noqa: E501
"""EV5 and EV6 on the API side: the mirror to each person's inbox is exact, never blocks a request,
retries after an outage without duplicating, and is honest about what is waiting."""
import uuid
from datetime import timedelta

from sqlalchemy import text

from app.main import app
from app.services.inbox import RETENTION, NullInbox, deliver, get_inbox, sweep
from tests.helpers import ADMIN, FACTORY, T1, fund, scalar

ONE_FARMER = {"X-Dev-Uid": "mirror-farmer", "X-Dev-Phone": "+923008886789"}


async def waiting(api) -> int:
    return await scalar(
        api,
        "SELECT count(*) FROM notifications WHERE delivered_at IS NULL AND recipient_uid IS NOT NULL AND created_at >= now() - interval '1 minute'",
    )


async def test_funding_mirrors_exactly_the_right_people_with_the_notification_id_as_the_doc_id(api, world):
    seen = len(api.inbox.docs)  # the lot that the fixture reported was mirrored already
    await api.session.execute(text("UPDATE notifications SET created_at = created_at - interval '1 hour'"))
    await fund(api, world)
    docs = api.inbox.docs[seen:]
    assert docs, "nothing was mirrored"
    rows = (await api.session.execute(
        text("SELECT id, recipient_uid, title, body, created_at, delivered_at FROM notifications WHERE created_at >= now() - interval '1 minute' AND recipient_uid IS NOT NULL")
    )).all()
    assert {str(r.id) for r in rows} == {d.id for d in docs}  # one doc per notification, same id
    assert {d.uid for d in docs} == {r.recipient_uid for r in rows}
    assert "t-factory" not in {d.uid for d in docs}  # the factory funded it: it is not told
    assert "t-trans1" in {d.uid for d in docs}  # the transporter who was offered the load
    assert all(r.delivered_at is not None for r in rows)
    by_id = {d.id: d for d in docs}
    for r in rows:
        d = by_id[str(r.id)]
        assert (d.title, d.body) == (r.title, r.body)
        assert d.fields()["expires_at"] == r.created_at + RETENTION == r.created_at + timedelta(days=30)
    assert await waiting(api) == 0


async def test_a_firestore_outage_never_fails_the_request_and_the_sweeper_delivers_once(api, world):
    seen = len(api.inbox.docs)
    await api.session.execute(text("UPDATE notifications SET created_at = created_at - interval '1 hour'"))
    api.inbox.fail = True
    r = await api.post(f"/api/jobs/{world.job_id}/fund", headers=FACTORY)
    assert r.status_code == 200 and r.json()["state"] == "offered"  # Postgres has the truth
    assert len(api.inbox.docs) == seen  # nothing new reached Firestore
    stuck = await waiting(api)
    assert stuck >= 2  # at least an admin and the offered transporter
    stats = (await api.get("/api/stats", headers=ADMIN)).json()
    assert stats["notifications_undelivered"] >= stuck  # the admin can see it

    api.inbox.fail = False
    sent = await sweep(api.session, api.inbox)
    assert sent >= stuck and await waiting(api) == 0
    assert await sweep(api.session, api.inbox) == 0  # nothing left, nothing sent twice
    ids = [d.id for d in api.inbox.docs]
    assert len(ids) == len(set(ids))
    after = (await api.get("/api/stats", headers=ADMIN)).json()["notifications_undelivered"]
    assert after == stats["notifications_undelivered"] - sent


async def test_the_dispatch_tick_retries_what_failed(api, world):
    api.inbox.fail = True
    await api.post(f"/api/jobs/{world.job_id}/fund", headers=FACTORY)
    assert await waiting(api) > 0
    api.inbox.fail = False
    assert (await api.post("/api/dispatch/tick", headers=ADMIN)).status_code == 200
    assert await waiting(api) == 0


async def test_delivering_the_same_notifications_twice_writes_nothing_the_second_time(api, world):
    await fund(api, world)
    count = len(api.inbox.docs)
    ids = (await api.session.execute(text("SELECT id FROM notifications WHERE created_at >= now()"))).scalars().all()
    api.session.info["notification_ids"] = list(ids)
    assert await deliver(api.session, api.inbox) == 0  # already delivered
    assert len(api.inbox.docs) == count


async def test_when_firestore_is_not_configured_nothing_waits_and_nothing_is_counted(api, world):
    app.dependency_overrides[get_inbox] = lambda: NullInbox()
    try:
        await api.post(f"/api/jobs/{world.job_id}/fund", headers=FACTORY)
        assert await scalar(api, "SELECT count(*) FROM notifications WHERE created_at >= now()") > 0  # still recorded
        assert (await api.get("/api/stats", headers=ADMIN)).json()["notifications_undelivered"] == 0
        assert (await api.get("/api/notifications", headers=T1)).json()["items"]  # the bell works from Postgres
    finally:
        app.dependency_overrides[get_inbox] = lambda: api.inbox


async def test_a_farmer_who_only_phones_is_recorded_but_never_mirrored_or_counted(api, world):
    await fund(api, world)  # the world's farmer called in: no login
    phone_only = await scalar(
        api, "SELECT count(*) FROM notifications WHERE recipient_uid IS NULL AND recipient_farmer_id IS NOT NULL AND created_at >= now()"
    )
    assert phone_only >= 1
    assert all(d.uid for d in api.inbox.docs)  # only people with a login have an inbox
    stats = (await api.get("/api/stats", headers=ADMIN)).json()
    assert stats["notifications_undelivered"] == 0  # they would otherwise wait forever


async def test_the_mirror_contains_only_what_the_recipient_may_know(api, world):
    await api.post("/api/me/register", headers=ONE_FARMER, json={"role": "farmer", "display_name": "Mirror Farmer"})
    await api.post(
        "/api/lots/mine", headers={**ONE_FARMER, "Idempotency-Key": "mirror-1"},
        json={"residue_type": "rice_straw", "quantity_tonnes": 2.5, "pickup_date": __import__("tests.helpers", fromlist=["tomorrow"]).tomorrow(),
              "pickup_part": "morning", "village": "Raiwind", "district": "Lahore"},
    )
    for d in api.inbox.docs:
        text_ = f"{d.title} {d.body} {d.type}"
        assert "+92" not in text_ and "@" not in text_ and "Mirror Farmer" not in text_
        assert set(d.fields()) == {"type", "level", "title", "body", "job_id", "refresh", "created_at", "expires_at"}
        assert d.job_id is None or uuid.UUID(d.job_id)
    mine = [d for d in api.inbox.docs if d.uid == "mirror-farmer"]
    assert [d.type for d in mine] == ["lot.matched"]


async def test_me_tells_the_web_whether_live_updates_exist(api, world):
    assert (await api.get("/api/me", headers=ADMIN)).json()["live_updates"] is True  # the fake mirror is on
    app.dependency_overrides[get_inbox] = lambda: NullInbox()
    try:
        assert (await api.get("/api/me", headers=ADMIN)).json()["live_updates"] is False
    finally:
        app.dependency_overrides[get_inbox] = lambda: api.inbox
