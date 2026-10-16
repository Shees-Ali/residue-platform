# ruff: noqa: E501
"""EV5 against a real (emulated) Firestore. Skipped unless the emulator is running:

    firebase emulators:exec --only firestore --config deploy/firebase.json --project demo-residue \
        "cd api && python -m pytest -m emulator"
"""
import os
import uuid
from datetime import UTC, datetime

import httpx
import pytest
from sqlalchemy import text

from app.main import app
from app.services.inbox import FirestoreInbox, InboxDoc, get_inbox, sweep
from tests.helpers import ADMIN, FACTORY, fund, scalar

HOST = os.getenv("FIRESTORE_EMULATOR_HOST")
pytestmark = [
    pytest.mark.emulator,
    pytest.mark.skipif(not HOST, reason="FIRESTORE_EMULATOR_HOST not set (use firebase emulators:exec)"),
]
PROJECT = os.getenv("GCLOUD_PROJECT") or os.getenv("GOOGLE_CLOUD_PROJECT") or "demo-residue"


@pytest.fixture
async def firestore():
    """A real client on the emulator, with all data wiped before and after."""
    from google.cloud import firestore as fs

    async def wipe():
        async with httpx.AsyncClient() as http:
            await http.delete(f"http://{HOST}/emulator/v1/projects/{PROJECT}/databases/(default)/documents")

    await wipe()
    client = fs.AsyncClient(project=PROJECT)
    yield client
    await wipe()


def doc(uid: str, n: int = 1) -> InboxDoc:
    return InboxDoc(
        id=str(uuid.uuid4()), uid=uid, type="job.funded", level="info", title=f"Title {n}",
        body="Body", job_id=str(uuid.uuid4()), refresh=["jobs", "ledger"], created_at=datetime.now(UTC),
    )


async def inbox_of(client, uid):
    return {d.id: d.to_dict() async for d in client.collection("users").document(uid).collection("inbox").stream()}


async def test_a_write_lands_in_the_right_inbox_with_every_field_and_nowhere_else(firestore):
    a, b = doc("alice"), doc("bob")
    assert sorted(await FirestoreInbox().write([a, b])) == sorted([a.id, b.id])
    mine = await inbox_of(firestore, "alice")
    assert list(mine) == [a.id]
    data = mine[a.id]
    assert set(data) == {"type", "level", "title", "body", "job_id", "refresh", "created_at", "expires_at"}
    assert data["refresh"] == ["jobs", "ledger"] and data["title"] == "Title 1"
    assert (data["expires_at"] - data["created_at"]).days == 30
    assert list(await inbox_of(firestore, "bob")) == [b.id]
    assert await inbox_of(firestore, "carol") == {}


async def test_writing_the_same_notification_again_overwrites_it_and_never_duplicates(firestore):
    d = doc("alice")
    sink = FirestoreInbox()
    await sink.write([d])
    await sink.write([d])
    assert list(await inbox_of(firestore, "alice")) == [d.id]


async def test_a_large_batch_is_split_and_fully_written(firestore):
    docs = [doc("alice", n) for n in range(450)]  # more than one batch
    assert len(await FirestoreInbox().write(docs)) == 450
    assert len(await inbox_of(firestore, "alice")) == 450


async def test_the_whole_flow_fans_out_to_exactly_the_right_inboxes_and_the_sweeper_adds_nothing(api, world, firestore):
    real = FirestoreInbox()
    app.dependency_overrides[get_inbox] = lambda: real
    try:
        await fund(api, world)
        offered = await inbox_of(firestore, "t-trans1")
        assert [d["type"] for d in offered.values()] == ["offer.created"]
        assert await inbox_of(firestore, "t-trans2") == {}  # not offered yet
        assert "job.funded" not in [d["type"] for d in (await inbox_of(firestore, "t-factory")).values()]
        sent = await scalar(api, "SELECT count(*) FROM notifications WHERE delivered_at IS NOT NULL AND created_at >= now() - interval '1 minute'")
        assert sent >= 2
        before = {uid: await inbox_of(firestore, uid) for uid in ("t-trans1", "dev-admin")}
        assert await sweep(api.session, real) == 0  # everything was delivered the first time
        assert {uid: await inbox_of(firestore, uid) for uid in before} == before
    finally:
        app.dependency_overrides[get_inbox] = lambda: api.inbox


async def test_a_notification_that_failed_to_mirror_arrives_once_after_the_sweeper(api, world, firestore):
    real = FirestoreInbox()
    app.dependency_overrides[get_inbox] = lambda: api.inbox  # first: the fake that fails
    api.inbox.fail = True
    await api.post(f"/api/jobs/{world.job_id}/fund", headers=FACTORY)
    assert await inbox_of(firestore, "t-trans1") == {}
    api.inbox.fail = False
    assert await sweep(api.session, real) >= 1
    assert len(await inbox_of(firestore, "t-trans1")) == 1
    await sweep(api.session, real)
    assert len(await inbox_of(firestore, "t-trans1")) == 1
    stats = (await api.get("/api/stats", headers=ADMIN)).json()
    assert isinstance(stats["notifications_undelivered"], int)
    assert await scalar(api, "SELECT count(*) FROM notifications WHERE recipient_uid = 't-trans1' AND delivered_at IS NULL") == 0
    _ = text  # (sqlalchemy text kept for ad-hoc debugging queries)
