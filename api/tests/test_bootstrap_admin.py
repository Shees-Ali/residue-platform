"""A verified email in BOOTSTRAP_ADMIN_EMAILS is an admin on sign-in, with no signup form."""
import pytest
from sqlalchemy import text

from tests.helpers import scalar

BOSS = "boss-test@example.pk"


@pytest.fixture(autouse=True)
def _listed(monkeypatch):
    monkeypatch.setenv("BOOTSTRAP_ADMIN_EMAILS", BOSS)


def who(uid, email=None):
    h = {"X-Dev-Uid": uid}
    if email:
        h["X-Dev-Email"] = email
    return h


async def test_a_listed_email_is_admin_at_once_with_no_role_screen(api):
    r = await api.get("/api/me", headers=who("g-boss", BOSS))
    assert r.status_code == 200, r.text
    assert (r.json()["role"], r.json()["status"], r.json()["email"]) == ("admin", "active", BOSS)
    assert await scalar(api, "SELECT role FROM users WHERE uid = 'g-boss'") == "admin"


async def test_the_email_match_ignores_case(api):
    r = await api.get("/api/me", headers=who("g-case", BOSS.upper()))
    assert r.json()["role"] == "admin"


async def test_admin_routes_work_on_the_very_first_request(api):
    r = await api.get("/api/users?status=pending", headers=who("g-first", BOSS))
    assert r.status_code == 200, r.text


async def test_an_unlisted_email_still_has_to_sign_up(api):
    r = await api.get("/api/me", headers=who("g-other", "someone@gmail.com"))
    assert r.status_code == 404
    assert r.json()["detail"]["code"] == "not_registered"


async def test_no_email_claim_means_no_admin(api):
    assert (await api.get("/api/me", headers=who("g-noemail"))).status_code == 404


async def test_an_existing_non_admin_account_with_that_email_is_promoted(api):
    await api.post(
        "/api/me/register", headers=who("g-was-buyer"),
        json={"role": "buyer", "display_name": "Boss Buyer"},
    )
    await api.session.execute(
        text("UPDATE users SET email = :e WHERE uid = 'g-was-buyer'"), {"e": BOSS}
    )
    r = await api.get("/api/me", headers=who("g-was-buyer", BOSS))
    assert (r.json()["role"], r.json()["status"]) == ("admin", "active")


async def test_a_pending_factory_with_that_email_becomes_an_active_admin(api):
    await api.post(
        "/api/me/register", headers=who("g-was-factory"),
        json={
            "role": "factory", "display_name": "Mill", "village": "Raiwind", "district": "Lahore",
            "factory": {"name": "Mill", "price_per_tonne": 400000, "residues": ["rice_straw"]},
        },
    )
    await api.session.execute(
        text("UPDATE users SET email = :e WHERE uid = 'g-was-factory'"), {"e": BOSS}
    )
    r = await api.get("/api/me", headers=who("g-was-factory", BOSS))
    assert (r.json()["role"], r.json()["status"]) == ("admin", "active")


async def test_an_email_already_used_by_another_login_is_not_taken_over(api):
    await api.post(
        "/api/me/register", headers=who("g-owner", BOSS),
        json={"role": "buyer", "display_name": "Owner"},
    )
    # a second Firebase login (a different uid) presenting the same email must not clone the account
    await api.session.execute(text("UPDATE users SET role='buyer' WHERE uid='g-owner'"))
    r = await api.get("/api/me", headers=who("g-clone", BOSS))
    assert r.status_code == 404
