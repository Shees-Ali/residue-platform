# ruff: noqa: E501
"""EV4: the bell. Paging, unread, read, read all, privacy and every validation message."""
import uuid

import pytest
from sqlalchemy import text

from app.services.notify import emit

ME = {"X-Dev-Uid": "bell-me"}
OTHER = {"X-Dev-Uid": "bell-other"}


@pytest.fixture
async def bell(api, world):
    for uid in ("bell-me", "bell-other"):
        await api.session.execute(
            text("INSERT INTO users (uid, role) VALUES (:u, 'buyer')"), {"u": uid}
        )
    for _ in range(7):
        await emit(api.session, "account.edited", uid="bell-me")
    await emit(api.session, "account.edited", uid="bell-other")
    return api


def fields(r):
    return {e["field"]: e["message"] for e in r.json()["errors"]}


async def test_paging_walks_newest_first_without_gaps_or_repeats(bell):
    api = bell
    seen, cursor = [], None
    for _ in range(4):
        params = {"limit": 3, **({"before": cursor} if cursor else {})}
        page = (await api.get("/api/notifications", headers=ME, params=params)).json()
        seen += [n["id"] for n in page["items"]]
        assert page["unread"] == 7
        cursor = page["next"]
        if cursor is None:
            break
    assert len(seen) == len(set(seen)) == 7
    assert cursor is None  # the last page has no marker
    first = (await api.get("/api/notifications?limit=50", headers=ME)).json()["items"]
    assert [n["id"] for n in first] == seen  # newest first, the same order the pages gave
    assert all(n["title"] == "Details updated" and n["read"] is False and n["level"] == "info" for n in first)


async def test_read_marks_one_and_unread_only_hides_it(bell):
    api = bell
    items = (await api.get("/api/notifications?limit=50", headers=ME)).json()["items"]
    done = await api.post(f"/api/notifications/{items[0]['id']}/read", headers=ME)
    assert done.status_code == 204
    assert (await api.post(f"/api/notifications/{items[0]['id']}/read", headers=ME)).status_code == 204  # again is harmless
    assert (await api.get("/api/notifications/unread-count", headers=ME)).json() == {"unread": 6}
    unread = (await api.get("/api/notifications?unread_only=true&limit=50", headers=ME)).json()
    assert len(unread["items"]) == 6 and items[0]["id"] not in [n["id"] for n in unread["items"]]
    everything = (await api.get("/api/notifications?limit=50", headers=ME)).json()["items"]
    assert [n["read"] for n in everything].count(True) == 1


async def test_read_all_clears_the_badge_and_reports_how_many(bell):
    api = bell
    assert (await api.post("/api/notifications/read-all", headers=ME)).json() == {"marked": 7}
    assert (await api.post("/api/notifications/read-all", headers=ME)).json() == {"marked": 0}
    assert (await api.get("/api/notifications/unread-count", headers=ME)).json() == {"unread": 0}
    assert (await api.get("/api/notifications/unread-count", headers=OTHER)).json() == {"unread": 1}  # theirs untouched


async def test_nobody_sees_or_touches_anyone_elses_notifications(bell):
    api = bell
    mine = (await api.get("/api/notifications?limit=50", headers=ME)).json()["items"]
    theirs = (await api.get("/api/notifications?limit=50", headers=OTHER)).json()["items"]
    assert len(theirs) == 1 and not {n["id"] for n in mine} & {n["id"] for n in theirs}
    r = await api.post(f"/api/notifications/{theirs[0]['id']}/read", headers=ME)
    assert r.status_code == 404 and r.json()["detail"] == "Notification not found"  # never 403: no hint it exists
    assert (await api.get("/api/notifications/unread-count", headers=OTHER)).json() == {"unread": 1}
    for bad in ("not-a-uuid", str(uuid.uuid4())):
        r = await api.post(f"/api/notifications/{bad}/read", headers=ME)
        assert r.status_code == 404 and r.json()["detail"] == "Notification not found"


@pytest.mark.parametrize(
    "query, field, message",
    [
        ("limit=0", "limit", "Limit must be between 1 and 50"),
        ("limit=51", "limit", "Limit must be between 1 and 50"),
        ("limit=-3", "limit", "Limit must be between 1 and 50"),
        ("before=abc", "before", "That page marker is not valid"),
        ("before=12.zz", "before", "That page marker is not valid"),
        ("before=" + "9" * 65, "before", "That page marker is not valid"),
        ("unread_only=maybe", "unread_only", "Unread only must be true or false"),
    ],
)
async def test_a_bad_query_is_refused_with_a_message_that_names_the_field(bell, query, field, message):
    r = await bell.get(f"/api/notifications?{query}", headers=ME)
    assert r.status_code == 422, r.text
    assert fields(r)[field] == message


async def test_the_job_events_limit_has_its_own_message(bell):
    r = await bell.get(f"/api/jobs/{uuid.uuid4()}/events?limit=201", headers={"X-Dev-Uid": "dev-admin"})
    assert r.status_code == 422 and fields(r)["limit"] == "Limit must be between 1 and 200"


async def test_a_person_with_no_notifications_gets_an_empty_page(bell):
    await bell.session.execute(text("INSERT INTO users (uid, role) VALUES ('bell-new', 'buyer')"))
    page = (await bell.get("/api/notifications", headers={"X-Dev-Uid": "bell-new"})).json()
    assert page == {"items": [], "next": None, "unread": 0}
