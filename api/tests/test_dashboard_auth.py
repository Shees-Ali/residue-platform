"""Dashboard auth: Firebase token proves identity, the users table gives the role."""
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from app.auth import firebase
from app.auth.firebase import AuthUser, current_user, require_role


def db_returning(role, status="active"):
    result = MagicMock()
    result.first.return_value = None if role is None else (role, status)
    session = MagicMock()
    session.execute = AsyncMock(return_value=result)
    return session


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.delenv("AUTH_DISABLED", raising=False)
    monkeypatch.delenv("VOICE_AUTH_DISABLED", raising=False)
    monkeypatch.delenv("K_SERVICE", raising=False)
    monkeypatch.setattr(firebase, "get_settings", lambda: SimpleNamespace(firebase_project_id="p"))


async def test_missing_or_malformed_token_is_401():
    for header in (None, "Basic abc", ""):
        with pytest.raises(HTTPException) as e:
            await current_user(db_returning("admin"), header, None)
        assert e.value.status_code == 401


async def test_invalid_token_is_401(monkeypatch):
    def boom(token, project):
        raise ValueError("expired")

    monkeypatch.setattr(firebase, "_verify", boom)
    with pytest.raises(HTTPException) as e:
        await current_user(db_returning("admin"), "Bearer x", None)
    assert e.value.status_code == 401


async def test_valid_token_takes_the_role_from_the_users_table(monkeypatch):
    seen = {}

    def fake(token, project):
        seen["project"] = project
        return {"sub": "uid-1"}

    monkeypatch.setattr(firebase, "_verify", fake)
    user = await current_user(db_returning("factory"), "Bearer good", None)
    assert user == AuthUser("uid-1", "factory")
    assert seen["project"] == "p"


async def test_a_valid_token_without_a_users_row_is_403(monkeypatch):
    monkeypatch.setattr(firebase, "_verify", lambda t, p: {"sub": "stranger"})
    with pytest.raises(HTTPException) as e:
        await current_user(db_returning(None), "Bearer good", None)
    assert e.value.status_code == 403
    assert e.value.detail["code"] == "not_registered"


async def test_a_pending_account_is_403_pending_approval(monkeypatch):
    monkeypatch.setattr(firebase, "_verify", lambda t, p: {"sub": "u"})
    with pytest.raises(HTTPException) as e:
        await current_user(db_returning("factory", "pending"), "Bearer good", None)
    assert e.value.status_code == 403
    assert e.value.detail["code"] == "pending_approval"


async def test_a_suspended_account_is_403(monkeypatch):
    monkeypatch.setattr(firebase, "_verify", lambda t, p: {"sub": "u"})
    with pytest.raises(HTTPException) as e:
        await current_user(db_returning("buyer", "suspended"), "Bearer good", None)
    assert e.value.detail["code"] == "suspended"


async def test_verified_claims_carry_email_and_phone(monkeypatch):
    monkeypatch.setattr(
        firebase,
        "_verify",
        lambda t, p: {
            "sub": "u", "email": "a@b.pk", "email_verified": True, "phone_number": "+923001",
        },
    )
    claims = await firebase.verified_claims("Bearer good", None)
    assert (claims.uid, claims.email, claims.email_verified, claims.phone) == (
        "u", "a@b.pk", True, "+923001",
    )


async def test_bypass_defaults_to_dev_admin_without_touching_the_database(monkeypatch):
    monkeypatch.setenv("AUTH_DISABLED", "true")
    db = db_returning(None)
    assert await current_user(db, None, None) == AuthUser("dev-admin", "admin")
    db.execute.assert_not_called()


async def test_bypass_can_pick_a_seeded_user(monkeypatch):
    monkeypatch.setenv("AUTH_DISABLED", "true")
    assert await current_user(db_returning("transporter"), None, "dev-transporter-1") == AuthUser(
        "dev-transporter-1", "transporter"
    )


async def test_bypass_is_ignored_on_cloud_run(monkeypatch):
    monkeypatch.setenv("AUTH_DISABLED", "true")
    monkeypatch.setenv("K_SERVICE", "residue-api")
    with pytest.raises(HTTPException) as e:
        await current_user(db_returning("admin"), None, "dev-admin")
    assert e.value.status_code == 401


async def test_require_role_allows_listed_roles_only():
    check = require_role("admin", "factory")
    assert await check(AuthUser("u", "factory")) == AuthUser("u", "factory")
    with pytest.raises(HTTPException) as e:
        await check(AuthUser("u", "buyer"))
    assert e.value.status_code == 403


async def test_a_slow_clock_gets_a_helpful_401(monkeypatch):
    def early(token, project):
        raise ValueError("Token used too early, 100 < 140. Check your clock.")

    monkeypatch.setattr(firebase, "_verify", early)
    with pytest.raises(HTTPException) as e:
        await current_user(db_returning("admin"), "Bearer x", None)
    assert e.value.status_code == 401
    assert "clock" in e.value.detail


def test_clock_skew_allowance_defaults_to_a_minute_and_is_configurable(monkeypatch):
    monkeypatch.delenv("AUTH_CLOCK_SKEW_SECONDS", raising=False)
    assert firebase.clock_skew_seconds() == 60
    monkeypatch.setenv("AUTH_CLOCK_SKEW_SECONDS", "5")
    assert firebase.clock_skew_seconds() == 5
