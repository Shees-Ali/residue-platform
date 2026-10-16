import pytest
from fastapi import HTTPException

from app.auth.idempotency import require_idempotency_key
from app.main import app
from app.models import agent as agent_models


def test_agent_routes_are_exactly_the_four_tools():
    ops = {
        (path, method.upper())
        for path, item in app.openapi()["paths"].items()
        if path.startswith("/api/agent")
        for method in item
    }
    assert ops == {
        ("/api/agent/lots", "POST"),
        ("/api/agent/quote", "POST"),
        ("/api/agent/escalations", "POST"),
        ("/api/agent/confirmations", "POST"),
    }


def test_agent_request_models_have_no_farmer_identity():
    for name in ("CreateLotIn", "GetQuoteIn", "EscalateIn", "RecordConfirmationIn"):
        fields = getattr(agent_models, name).model_fields
        assert "call_id" in fields
        assert not [f for f in fields if "farmer" in f or "phone" in f]


def test_agent_routes_reject_unauthenticated(client, monkeypatch):
    monkeypatch.delenv("AUTH_DISABLED", raising=False)
    monkeypatch.delenv("VOICE_AUTH_DISABLED", raising=False)
    r = client.post("/api/agent/lots", json={})
    assert r.status_code == 401


async def test_idempotency_key_required():
    with pytest.raises(HTTPException) as e:
        await require_idempotency_key(None)
    assert e.value.status_code == 400


def test_voice_auth_bypass_does_not_make_callers_admin(monkeypatch):
    """VOICE_AUTH_DISABLED opens only the voice routes: a user route still needs a token."""
    from app.config import auth_bypass_active, voice_auth_bypass_active

    monkeypatch.delenv("K_SERVICE", raising=False)
    monkeypatch.delenv("AUTH_DISABLED", raising=False)
    monkeypatch.delenv("VOICE_AUTH_DISABLED", raising=False)
    monkeypatch.setenv("VOICE_AUTH_DISABLED", "true")
    assert voice_auth_bypass_active() and not auth_bypass_active()
    monkeypatch.setenv("K_SERVICE", "residue-api")  # Cloud Run: never honoured
    assert not voice_auth_bypass_active()
