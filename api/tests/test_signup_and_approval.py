"""Self-signup, admin approval, and what each new role may see. Bypass mode: X-Dev-* stand in for
a verified Firebase token (uid, email, phone)."""
from app.services.assignment_store import load_factories
from tests.helpers import ADMIN, FARMER_ESTIMATE, scalar


def who(uid, email=None, phone=None):
    h = {"X-Dev-Uid": uid}
    if email:
        h["X-Dev-Email"] = email
    if phone:
        h["X-Dev-Phone"] = phone
    return h


async def reg(api, uid, body):
    return await api.post("/api/me/register", headers=who(uid), json=body)


FACTORY_BODY = {
    "role": "factory",
    "display_name": "New Mill",
    "village": "Raiwind",
    "district": "Lahore",
    "factory": {"name": "New Mill", "price_per_tonne": 4_000_000, "residues": ["rice_straw"]},
}
TRANSPORTER_BODY = {
    "role": "transporter",
    "display_name": "Truck Co",
    "phone": "+923009990001",
    "village": "Raiwind",
    "district": "Lahore",
}


async def test_a_valid_token_without_a_profile_must_sign_up(api):
    r = await api.get("/api/me", headers=who("new-1"))
    assert r.status_code == 404
    assert r.json()["detail"]["code"] == "not_registered"
    other = await api.get("/api/offers", headers=who("new-1"))  # any role-gated route
    assert other.status_code == 403
    assert other.json()["detail"]["code"] == "not_registered"


async def test_buyer_is_active_at_once_and_cannot_reach_admin_routes(api):
    r = await api.post(
        "/api/me/register",
        headers=who("b-1", "buyer@x.pk"),
        json={"role": "buyer", "display_name": "Bilal"},
    )
    assert r.status_code == 201, r.text
    assert (r.json()["role"], r.json()["status"]) == ("buyer", "active")
    me = await api.get("/api/me", headers=who("b-1"))
    assert me.json()["email"] == "buyer@x.pk"
    assert (await api.get("/api/products", headers=who("b-1"))).status_code == 200
    assert (await api.get("/api/users", headers=who("b-1"))).status_code == 403


async def test_cannot_register_twice_or_as_admin(api):
    body = {"role": "buyer", "display_name": "Bilal"}
    assert (await reg(api, "b-2", body)).status_code == 201
    assert (await reg(api, "b-2", body)).status_code == 409
    admin = {"role": "admin", "display_name": "Sneaky"}
    assert (await reg(api, "b-3", admin)).status_code == 422


async def test_same_email_cannot_register_two_accounts(api):
    body = {"role": "buyer", "display_name": "Aa"}
    h1, h2 = who("e-1", "same@x.pk"), who("e-2", "same@x.pk")
    assert (await api.post("/api/me/register", headers=h1, json=body)).status_code == 201
    assert (await api.post("/api/me/register", headers=h2, json=body)).status_code == 409


async def test_only_a_bootstrap_email_that_is_verified_becomes_admin(api, monkeypatch):
    monkeypatch.setenv("BOOTSTRAP_ADMIN_EMAILS", "Boss@x.pk, other@x.pk")
    body = {"role": "buyer", "display_name": "Boss"}
    r = await api.post("/api/me/register", headers=who("boss", "boss@x.pk"), json=body)
    assert (r.json()["role"], r.json()["status"]) == ("admin", "active")
    assert (await api.get("/api/users", headers=who("boss"))).status_code == 200
    r = await api.post("/api/me/register", headers=who("rando", "rando@x.pk"), json=body)
    assert r.json()["role"] == "buyer"
    # no email claim at all (the dev bypass marks an email verified only when it is present)
    r = await api.post("/api/me/register", headers=who("noemail"), json=body)
    assert r.json()["role"] == "buyer"


async def test_transporter_waits_for_approval_then_gets_offers(api):
    r = await api.post("/api/me/register", headers=who("tr-1"), json=TRANSPORTER_BODY)
    assert r.status_code == 201, r.text
    assert r.json()["status"] == "pending"
    blocked = await api.get("/api/offers", headers=who("tr-1"))
    assert blocked.status_code == 403
    assert blocked.json()["detail"]["code"] == "pending_approval"
    me = await api.get("/api/me", headers=who("tr-1"))  # /me still works so the UI can show it
    assert me.json()["status"] == "pending"

    queue = (await api.get("/api/users?status=pending", headers=ADMIN)).json()
    mine = next(u for u in queue if u["uid"] == "tr-1")
    assert mine["details"]["tier"] == 1

    ok = await api.post("/api/users/tr-1/approve", headers=ADMIN, json={"tier": 2})
    assert ok.status_code == 200, ok.text
    assert ok.json()["status"] == "active"
    assert ok.json()["details"]["max_tonnes"] == 7
    assert await scalar(
        api, "SELECT approved_at IS NOT NULL FROM transporters WHERE user_uid = 'tr-1'"
    )
    assert (await api.get("/api/offers", headers=who("tr-1"))).status_code == 200


async def test_transporter_signup_needs_phone_and_a_place(api):
    no_phone = {k: v for k, v in TRANSPORTER_BODY.items() if k != "phone"}
    assert (await reg(api, "tr-2", no_phone)).status_code == 422
    no_place = {k: v for k, v in TRANSPORTER_BODY.items() if k not in ("village", "district")}
    assert (await reg(api, "tr-3", no_place)).status_code == 422
    bad = {**TRANSPORTER_BODY, "district": "Atlantis"}
    assert (await reg(api, "tr-4", bad)).status_code == 422
    # a failed signup leaves nothing behind, so the person can try again
    assert (await api.get("/api/me", headers=who("tr-2"))).status_code == 404


async def test_pending_factory_is_never_assigned_lots_until_approved(api):
    r = await api.post("/api/me/register", headers=who("f-1"), json=FACTORY_BODY)
    assert r.status_code == 201, r.text
    assert r.json()["status"] == "pending"
    fid = str(await scalar(api, "SELECT id FROM factories WHERE user_uid = 'f-1'"))
    assert fid not in {f.id for f in await load_factories(api.session)}
    assert (await api.post("/api/users/f-1/approve", headers=ADMIN)).status_code == 200
    assert fid in {f.id for f in await load_factories(api.session)}


async def test_factory_signup_validates_residues_and_requires_details(api):
    bad = {**FACTORY_BODY, "factory": {**FACTORY_BODY["factory"], "residues": ["gold"]}}
    assert (await reg(api, "f-2", bad)).status_code == 422
    bare = {k: v for k, v in FACTORY_BODY.items() if k != "factory"}
    assert (await reg(api, "f-3", bare)).status_code == 422


async def test_reject_suspend_and_reactivate(api):
    await api.post("/api/me/register", headers=who("tr-5"), json=TRANSPORTER_BODY)
    assert (await api.post("/api/users/tr-5/reject", headers=ADMIN)).json()["status"] == "suspended"
    again = await api.post("/api/users/tr-5/approve", headers=ADMIN)
    assert again.status_code == 409  # only pending accounts can be approved
    blocked = await api.get("/api/offers", headers=who("tr-5"))
    assert blocked.json()["detail"]["code"] == "suspended"

    back = await api.post("/api/users/tr-5/reactivate", headers=ADMIN)
    assert back.json()["status"] == "active"
    out = await api.post("/api/users/tr-5/suspend", headers=ADMIN)
    assert out.json()["status"] == "suspended"
    assert not await scalar(
        api, "SELECT approved_at IS NOT NULL FROM transporters WHERE user_uid = 'tr-5'"
    )


async def test_admin_cannot_suspend_themselves_and_unknown_uid_is_404(api):
    assert (await api.post("/api/users/dev-admin/suspend", headers=ADMIN)).status_code == 409
    assert (await api.post("/api/users/nobody/approve", headers=ADMIN)).status_code == 404


async def test_only_admins_manage_users(api):
    await api.post(
        "/api/me/register", headers=who("b-9"), json={"role": "buyer", "display_name": "Ba"}
    )
    for path in ("/api/users/b-9/suspend", "/api/users/b-9/approve"):
        assert (await api.post(path, headers=who("b-9"))).status_code == 403


# --- farmers ------------------------------------------------------------------------------


async def test_farmer_links_to_the_record_for_their_verified_phone(api, world):
    h = who("farm-1", phone=world.farmer_phone)
    r = await api.post("/api/me/register", headers=h, json={"role": "farmer", "display_name": "Fa"})
    assert (r.json()["status"], r.json()["farmer_linked"]) == ("active", True)
    lots = (await api.get("/api/lots", headers=h)).json()
    assert [lot["id"] for lot in lots] == [world.lot_id]
    assert (await api.get(f"/api/lots/{world.lot_id}", headers=h)).status_code == 200


async def test_farmer_without_a_verified_phone_sees_nothing(api, world, sms_required):
    h = who("farm-2")
    r = await api.post("/api/me/register", headers=h, json={"role": "farmer", "display_name": "Fa"})
    assert r.json()["farmer_linked"] is False
    assert (await api.get("/api/lots", headers=h)).json() == []
    assert (await api.get(f"/api/lots/{world.lot_id}", headers=h)).status_code == 404


async def test_a_farmer_cannot_see_or_claim_someone_elses_lots(api, world):
    h = who("farm-3", phone="+923007770001")  # a new farmer, different phone
    await api.post("/api/me/register", headers=h, json={"role": "farmer", "display_name": "Ga"})
    assert (await api.get("/api/lots", headers=h)).json() == []
    assert (await api.get(f"/api/lots/{world.lot_id}", headers=h)).status_code == 404
    # the phone is already taken by the first account
    await api.post(
        "/api/me/register",
        headers=who("farm-4", phone=world.farmer_phone),
        json={"role": "farmer", "display_name": "Fa"},
    )
    dup = await api.post(
        "/api/me/register",
        headers=who("farm-5", phone=world.farmer_phone),
        json={"role": "farmer", "display_name": "Imposter"},
    )
    assert dup.status_code == 409


async def test_farmer_payout_is_pending_with_the_quoted_estimate(api, world):
    h = who("farm-6", phone=world.farmer_phone)
    await api.post("/api/me/register", headers=h, json={"role": "farmer", "display_name": "Fa"})
    payouts = (await api.get("/api/ledger/mine", headers=h)).json()
    assert payouts == [
        {
            "job_id": world.job_id,
            "state": "created",
            "status": "pending",
            "amount": FARMER_ESTIMATE,
        }
    ]


async def test_farmers_cannot_use_other_roles_routes(api, world):
    h = who("farm-7", phone=world.farmer_phone)
    await api.post("/api/me/register", headers=h, json={"role": "farmer", "display_name": "Fa"})
    for method, path in (
        ("get", "/api/offers"),
        ("get", "/api/orders"),  # the shelf itself is public; orders are not
        ("get", "/api/ledger"),
        ("get", "/api/users"),
        ("get", f"/api/lots/{world.lot_id}/ranking"),
    ):
        r = await getattr(api, method)(path, headers=h)
        assert r.status_code == 403, (path, r.status_code)


async def test_impact_records_name_farmers_so_only_admins_get_them(api, world):
    await api.post(
        "/api/me/register", headers=who("b-10"), json={"role": "buyer", "display_name": "Ba"}
    )
    assert (await api.get("/api/impact", headers=who("b-10"))).json()["records"] == []
    assert "records" in (await api.get("/api/impact", headers=ADMIN)).json()
