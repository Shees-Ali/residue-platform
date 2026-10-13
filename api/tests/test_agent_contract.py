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


def test_agent_routes_reject_unauthenticated(client):
    r = client.post("/api/agent/lots", json={})
    assert r.status_code in (401, 501)  # TODO(F1): tighten to 401 once OIDC verify exists


async def test_idempotency_key_required():
    with pytest.raises(HTTPException) as e:
        await require_idempotency_key(None)
    assert e.value.status_code == 400
