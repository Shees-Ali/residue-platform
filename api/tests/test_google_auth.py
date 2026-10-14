"""Voice-service auth: Google ID token checks and the local-only bypass."""
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.auth import google_oidc
from app.auth.google_oidc import voice_service_caller

VOICE_SA = "residue-voice@proj.iam.gserviceaccount.com"


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    monkeypatch.delenv("AUTH_DISABLED", raising=False)
    monkeypatch.delenv("K_SERVICE", raising=False)
    monkeypatch.setattr(
        google_oidc,
        "get_settings",
        lambda: SimpleNamespace(voice_service_account=VOICE_SA, api_audience="https://api"),
    )


async def test_missing_token_is_401():
    with pytest.raises(HTTPException) as e:
        await voice_service_caller(None)
    assert e.value.status_code == 401


async def test_non_bearer_header_is_401():
    with pytest.raises(HTTPException) as e:
        await voice_service_caller("Basic abc")
    assert e.value.status_code == 401


async def test_invalid_token_is_401(monkeypatch):
    def boom(token, audience):
        raise ValueError("bad signature")

    monkeypatch.setattr(google_oidc, "_verify", boom)
    with pytest.raises(HTTPException) as e:
        await voice_service_caller("Bearer nope")
    assert e.value.status_code == 401


async def test_other_service_account_is_403(monkeypatch):
    monkeypatch.setattr(
        google_oidc, "_verify", lambda t, a: {"email": "evil@x.com", "email_verified": True}
    )
    with pytest.raises(HTTPException) as e:
        await voice_service_caller("Bearer ok")
    assert e.value.status_code == 403


async def test_unverified_email_is_403(monkeypatch):
    monkeypatch.setattr(
        google_oidc, "_verify", lambda t, a: {"email": VOICE_SA, "email_verified": False}
    )
    with pytest.raises(HTTPException) as e:
        await voice_service_caller("Bearer ok")
    assert e.value.status_code == 403


async def test_voice_service_account_passes_and_audience_is_checked(monkeypatch):
    seen = {}

    def fake(token, audience):
        seen["audience"] = audience
        return {"email": VOICE_SA, "email_verified": True}

    monkeypatch.setattr(google_oidc, "_verify", fake)
    assert await voice_service_caller("Bearer ok") == VOICE_SA
    assert seen["audience"] == "https://api"


async def test_bypass_works_locally(monkeypatch):
    monkeypatch.setenv("AUTH_DISABLED", "true")
    assert await voice_service_caller(None) == "local-dev"


async def test_bypass_is_refused_on_cloud_run(monkeypatch):
    monkeypatch.setenv("AUTH_DISABLED", "true")
    monkeypatch.setenv("K_SERVICE", "residue-api")
    with pytest.raises(HTTPException) as e:
        await voice_service_caller(None)
    assert e.value.status_code == 401


def test_agent_and_internal_routes_reject_missing_token(client):
    assert client.post("/api/agent/lots", json={}).status_code == 401
    assert client.post("/api/internal/calls", json={}).status_code == 401
