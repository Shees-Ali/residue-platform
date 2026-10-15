"""Every dashboard route against every role. A new /api route must be added to ROUTES, so it
cannot ship without someone deciding who may call it."""
import re

import pytest
from sqlalchemy import text

from app.auth import firebase, google_oidc
from app.main import app

ZERO = "00000000-0000-0000-0000-000000000000"
ROLES = ("admin", "factory", "transporter", "buyer", "farmer")
HEADERS = {
    "admin": {"X-Dev-Uid": "dev-admin"},
    "factory": {"X-Dev-Uid": "dev-factory-0"},
    "transporter": {"X-Dev-Uid": "dev-transporter-0"},
    "buyer": {"X-Dev-Uid": "dev-buyer-0"},
    "farmer": {"X-Dev-Uid": "matrix-farmer"},
}
ADMIN = {"admin"}
ALL_BUT_FARMER_BUYER = {"admin", "factory", "transporter"}

# (method, path template) -> (roles allowed, json body for routes that check a role in the handler)
ROUTES: dict[tuple[str, str], tuple[set[str], dict | None]] = {
    ("GET", "/api/lots"): ({"admin", "farmer"}, None),
    ("POST", "/api/lots"): (ADMIN, None),
    ("POST", "/api/lots/mine"): ({"farmer"}, None),
    ("GET", "/api/residue-types"): (set(ROLES), None),
    ("GET", "/api/districts"): (set(ROLES), None),
    ("GET", "/api/villages"): (set(ROLES), None),
    ("GET", "/api/lots/{lot_id}"): ({"admin", "farmer"}, None),
    ("GET", "/api/lots/{lot_id}/ranking"): (ADMIN, None),
    ("POST", "/api/lots/{lot_id}/override"): (ADMIN, None),
    ("GET", "/api/jobs"): (ALL_BUT_FARMER_BUYER | {"farmer"}, None),
    ("GET", "/api/jobs/{job_id}"): (ALL_BUT_FARMER_BUYER | {"farmer"}, None),
    ("GET", "/api/jobs/{job_id}/offers"): (ADMIN, None),
    ("GET", "/api/stats"): (ADMIN, None),
    ("POST", "/api/offers/{offer_id}/decline"): ({"transporter"}, None),
    ("POST", "/api/jobs/{job_id}/fund"): ({"factory"}, None),
    ("POST", "/api/jobs/{job_id}/redispatch"): (ADMIN, None),
    ("POST", "/api/jobs/{job_id}/photos/upload-url"): ({"transporter"}, {"kind": "pickup"}),
    ("POST", "/api/jobs/{job_id}/pickup"): ({"transporter"}, None),
    ("POST", "/api/jobs/{job_id}/deliver"): ({"transporter"}, None),
    ("POST", "/api/jobs/{job_id}/location"): ({"transporter"}, None),
    ("POST", "/api/jobs/{job_id}/verify"): ({"farmer"}, None),
    ("GET", "/api/jobs/{job_id}/ledger"): ({"admin", "factory"}, None),
    ("GET", "/api/jobs/{job_id}/track"): ({"admin", "factory"}, None),
    ("GET", "/api/tracking/active"): ({"admin", "factory"}, None),
    ("POST", "/api/jobs/{job_id}/grade"): ({"factory"}, None),
    ("POST", "/api/jobs/{job_id}/confirm"): ({"factory"}, None),
    ("POST", "/api/jobs/{job_id}/verification-call"): (ADMIN, None),
    ("GET", "/api/offers"): ({"transporter"}, None),
    ("POST", "/api/offers/{offer_id}/accept"): ({"transporter"}, None),
    ("GET", "/api/ledger"): (ADMIN, None),
    ("GET", "/api/ledger/check"): (ADMIN, None),
    ("GET", "/api/ledger/mine"): ({"transporter", "farmer"}, None),
    ("GET", "/api/products"): ({"buyer", "factory", "admin"}, None),
    ("POST", "/api/products"): ({"factory"}, None),
    ("PATCH", "/api/products/{product_id}"): ({"factory"}, None),
    ("POST", "/api/orders"): ({"buyer"}, None),
    ("GET", "/api/orders"): ({"buyer", "factory", "admin"}, None),
    ("GET", "/api/orders/{order_id}/split"): ({"buyer", "factory", "admin"}, None),
    ("POST", "/api/dispatch/tick"): (ADMIN, None),
    ("GET", "/api/escalations"): (ADMIN, None),
    ("POST", "/api/escalations/{escalation_id}/resolve"): (ADMIN, None),
    ("GET", "/api/impact"): (set(ROLES), None),  # totals for all; farmer names only for admin
    ("GET", "/api/transporters"): (ADMIN, None),
    ("POST", "/api/transporters/{transporter_id}/approve"): (ADMIN, None),
    ("POST", "/api/transporters/{transporter_id}/revoke"): (ADMIN, None),
    ("GET", "/api/users"): (ADMIN, None),
    ("POST", "/api/users/{uid}/approve"): (ADMIN, None),
    ("POST", "/api/users/{uid}/reject"): (ADMIN, None),
    ("POST", "/api/users/{uid}/suspend"): (ADMIN, None),
    ("POST", "/api/users/{uid}/reactivate"): (ADMIN, None),
}
# Any signed-in person, including one who has not picked a role yet.
SELF_ROUTES = {("GET", "/api/me"), ("POST", "/api/me/register")}
# Needs a signed-in farmer (their own token phone), so it is covered in test_lot_forms.
FARMER_ONLY_ROUTES = {("POST", "/api/me/link-phone")}
# The local photo store: writing needs any signed-in person, reading is open (an img tag cannot
# send a token). Covered in test_m2_delivery_tracking.
DEV_ROUTES = {("PUT", "/api/dev-upload/{path}"), ("GET", "/api/dev-upload/{path}")}
# Service-to-service: Google ID token of the voice service account, never a Firebase user token.
SERVICE_PREFIXES = ("/api/agent/", "/api/internal/")


def _url(template: str) -> str:
    return re.sub(r"\{uid\}", "ghost", re.sub(r"\{(?!uid)\w+\}", ZERO, template))


def _call(api, method, template, headers, body):
    kwargs = {"headers": headers}
    if method != "GET":
        kwargs["json"] = body if body is not None else {}
    return api.request(method, _url(template), **kwargs)


def test_every_dashboard_route_is_in_the_matrix():
    # The OpenAPI schema lists every route whatever the FastAPI version does with routers.
    actual = {
        (method.upper(), path)
        for path, methods in app.openapi()["paths"].items()
        if path.startswith("/api") and not path.startswith(SERVICE_PREFIXES)
        for method in methods
        if method.upper() in ("GET", "POST", "PATCH", "PUT", "DELETE")
    }
    known = actual - SELF_ROUTES - FARMER_ONLY_ROUTES - DEV_ROUTES
    assert known == set(ROUTES), "add new routes to ROUTES with their roles"


@pytest.fixture
async def roles_ready(api):
    await api.session.execute(
        text(
            "INSERT INTO users (uid, role) VALUES ('matrix-farmer', 'farmer') "
            "ON CONFLICT DO NOTHING"
        )
    )


@pytest.mark.parametrize("role", ROLES)
async def test_each_role_may_call_only_its_routes(api, roles_ready, role):
    for (method, template), (allowed, body) in ROUTES.items():
        r = await _call(api, method, template, HEADERS[role], body)
        if role in allowed:
            assert r.status_code not in (401, 403), (role, method, template, r.status_code)
        else:
            assert r.status_code == 403, (role, method, template, r.status_code)


async def test_anonymous_callers_get_401_everywhere(api, monkeypatch):
    monkeypatch.delenv("AUTH_DISABLED")
    for (method, template), (_, body) in ROUTES.items():
        r = await _call(api, method, template, {}, body)
        assert r.status_code == 401, (method, template, r.status_code)
    for method, template in SELF_ROUTES:
        assert (await _call(api, method, template, {}, None)).status_code == 401


async def test_a_pending_account_is_blocked_everywhere_except_me(api, monkeypatch):
    await api.session.execute(
        text(
            "INSERT INTO users (uid, role, status) VALUES ('matrix-pending', 'factory', 'pending')"
        )
    )
    for (method, template), (_, body) in ROUTES.items():
        r = await _call(api, method, template, {"X-Dev-Uid": "matrix-pending"}, body)
        assert r.status_code == 403, (method, template, r.status_code)
        assert "pending_approval" in r.text, (method, template)
    assert (await api.get("/api/me", headers={"X-Dev-Uid": "matrix-pending"})).status_code == 200


async def test_a_firebase_user_token_does_not_open_the_service_routes(api, monkeypatch):
    monkeypatch.delenv("AUTH_DISABLED")
    monkeypatch.setattr(firebase, "_verify", lambda t, p: {"sub": "dev-admin"})

    def not_google(token, audience):
        raise ValueError("not a Google service-account token")

    monkeypatch.setattr(google_oidc, "_verify", not_google)
    headers = {"Authorization": "Bearer a-valid-firebase-admin-token"}
    for path in ("/api/agent/lots", "/api/agent/quote", "/api/internal/calls"):
        r = await api.post(path, headers={**headers, "Idempotency-Key": "k"}, json={})
        assert r.status_code in (401, 403), (path, r.status_code)
    # ...while the same token does work on a dashboard route
    assert (await api.get("/api/ledger/check", headers=headers)).status_code == 200
