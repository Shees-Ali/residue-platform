"""Field rules and the explicit error shape. Catalogue: memory/validation-rules.md."""
import pytest

from app.validation import normalize_phone
from tests.helpers import ADMIN, tomorrow


def who(uid, phone=None, email=None):
    h = {"X-Dev-Uid": uid}
    if phone:
        h["X-Dev-Phone"] = phone
    if email:
        h["X-Dev-Email"] = email
    return h


def fields(r) -> dict[str, str]:
    """{field: message} from a validation response, asserting the shape on the way."""
    body = r.json()
    assert isinstance(body["detail"], str) and body["detail"]
    assert all({"field", "message", "code"} <= set(e) for e in body["errors"])
    return {e["field"]: e["message"] for e in body["errors"]}


TRANSPORTER = {
    "role": "transporter", "display_name": "Truck Co", "phone": "+923009990001",
    "village": "Raiwind", "district": "Lahore",
}
FACTORY = {
    "role": "factory", "display_name": "Mill Owner", "village": "Raiwind", "district": "Lahore",
    "factory": {"name": "Green Mill", "price_per_tonne": 400_000, "residues": ["rice_straw"]},
}


# --- phone cleaning (pure) ---------------------------------------------------------------


@pytest.mark.parametrize(
    "typed, clean",
    [
        ("+923001234567", "+923001234567"),
        ("+92 300 123-4567", "+923001234567"),
        ("(+92) 300 1234567", "+923001234567"),
        ("03001234567", "+923001234567"),
        ("00923001234567", "+923001234567"),
    ],
)
def test_phones_are_cleaned_to_e164(typed, clean):
    assert normalize_phone(typed) == clean


@pytest.mark.parametrize("typed", ["", "abc", "12345", "+0123456789", "+92", "+9230012345678901"])
def test_bad_phones_say_what_is_expected(typed):
    with pytest.raises(ValueError, match="country code, like \\+923001234567"):
        normalize_phone(typed)


# --- the error shape ---------------------------------------------------------------------


async def test_a_missing_field_names_the_field(api):
    r = await api.post("/api/me/register", headers=who("v-1"), json={"role": "buyer"})
    assert r.status_code == 422
    assert fields(r) == {"display_name": "Name is required"}


async def test_every_problem_is_reported_at_once(api):
    r = await api.post(
        "/api/me/register", headers=who("v-2"), json={"role": "wizard", "display_name": "A"}
    )
    f = fields(r)
    assert f["role"].startswith("Role must be one of")
    assert f["display_name"] == "Name must be at least 2 characters"
    assert r.json()["detail"].startswith("Fix 2 fields:")


async def test_malformed_json_is_a_clear_422(api):
    r = await api.post(
        "/api/me/register", headers={**who("v-3"), "Content-Type": "application/json"}, content="{"
    )
    assert r.status_code == 422
    assert "JSON" in r.json()["detail"]


# --- register: per role ------------------------------------------------------------------


async def test_transporter_gaps_are_all_listed(api):
    r = await api.post("/api/me/register", headers=who("v-4"), json={
        "role": "transporter", "display_name": "Truck Co"})
    assert r.status_code == 422
    assert set(fields(r)) == {"phone", "village", "district"}
    assert "country code" in fields(r)["phone"]


async def test_a_typed_phone_is_cleaned_and_a_bad_one_is_refused(api):
    ok = await api.post(
        "/api/me/register", headers=who("v-5"), json={**TRANSPORTER, "phone": "0300 9990001"}
    )
    assert ok.status_code == 201
    assert ok.json()["phone"] == "+923009990001"
    bad = await api.post(
        "/api/me/register", headers=who("v-6"), json={**TRANSPORTER, "phone": "call me"}
    )
    assert fields(bad) == {"phone": "Phone must include the country code, like +923001234567"}


async def test_unknown_district_lists_the_valid_ones(api):
    r = await api.post(
        "/api/me/register", headers=who("v-7"), json={**TRANSPORTER, "district": "Atlantis"}
    )
    assert r.status_code == 422
    assert "district" in fields(r)
    assert "Lahore" in r.json()["valid"]


async def test_factory_without_details_lists_each_missing_field(api):
    body = {k: v for k, v in FACTORY.items() if k != "factory"}
    r = await api.post("/api/me/register", headers=who("v-8"), json=body)
    assert set(fields(r)) == {"factory.name", "factory.price_per_tonne", "factory.residues"}


@pytest.mark.parametrize("price", [0, 99, 100_000_001, -5])
async def test_price_outside_the_range_is_refused(api, price):
    body = {**FACTORY, "factory": {**FACTORY["factory"], "price_per_tonne": price}}
    r = await api.post("/api/me/register", headers=who(f"v-p{price}"), json=body)
    assert fields(r) == {
        "factory.price_per_tonne": "Price must be between PKR 1 and PKR 1,000,000 per tonne"
    }


@pytest.mark.parametrize(
    "residues, expect",
    [
        ([], "Choose at least 1 for residues"),
        (["rice_straw", "rice_straw"], "Residues must not repeat"),
        (["Rice Straw"], "Residues has an invalid format"),
        (["gold_dust"], "Unknown residue types: gold_dust"),
    ],
)
async def test_residue_list_rules(api, residues, expect):
    body = {**FACTORY, "factory": {**FACTORY["factory"], "residues": residues}}
    uid = f"v-r{len(residues)}{expect[:3]}"
    r = await api.post("/api/me/register", headers=who(uid), json=body)
    assert r.status_code == 422
    assert list(fields(r).values())[0].startswith(expect.split(":")[0])


async def test_a_phone_already_linked_to_a_farmer_is_a_409_on_the_phone_field(api):
    first = await api.post(
        "/api/me/register", headers=who("v-f1", phone="+923007770002"),
        json={"role": "farmer", "display_name": "Farah"},
    )
    assert first.status_code == 201
    r = await api.post(
        "/api/me/register", headers=who("v-f2", phone="+923007770002"),
        json={"role": "farmer", "display_name": "Fatima"},
    )
    assert r.status_code == 409
    assert fields(r) == {"phone": "That phone number is already linked to another account"}


async def test_an_email_already_registered_is_a_409_on_the_email_field(api):
    body = {"role": "buyer", "display_name": "Bilal"}
    await api.post("/api/me/register", headers=who("v-e1", email="dup@x.pk"), json=body)
    r = await api.post("/api/me/register", headers=who("v-e2", email="dup@x.pk"), json=body)
    assert r.status_code == 409
    assert fields(r) == {"email": "That email is already registered"}


async def test_a_rejected_signup_leaves_nothing_behind(api):
    bad = {**TRANSPORTER, "district": "Atlantis"}
    await api.post("/api/me/register", headers=who("v-9"), json=bad)
    assert (await api.get("/api/me", headers=who("v-9"))).status_code == 404


# --- other wired fields -----------------------------------------------------------------


@pytest.mark.parametrize("tier", [0, 4, "high", None, True])
async def test_tier_must_be_1_to_3(api, tier):
    r = await api.post("/api/users/dev-buyer-0/approve", headers=ADMIN, json={"tier": tier})
    assert r.status_code == 422
    assert fields(r) == {"tier": "Tier must be 1, 2 or 3"}


async def test_user_filters_name_the_allowed_values(api):
    r = await api.get("/api/users?status=maybe", headers=ADMIN)
    assert r.status_code == 422
    assert fields(r)["status"].startswith("Status must be one of")
    assert (await api.get("/api/users?role=wizard", headers=ADMIN)).status_code == 422


async def test_admin_lot_entry_checks_the_farmer_phone(api):
    body = {
        "farmer_phone": "not a phone", "residue_type": "rice_straw", "quantity_tonnes": 2,
        "pickup_date": tomorrow(), "pickup_part": "morning", "village": "Raiwind",
        "district": "Lahore",
    }
    r = await api.post("/api/lots", headers=ADMIN, json=body)
    assert r.status_code == 422
    assert fields(r) == {"farmer_phone": "Phone must include the country code, like +923001234567"}
    ok = await api.post("/api/lots", headers=ADMIN, json={**body, "farmer_phone": "03005550101"})
    assert ok.status_code == 201


async def test_override_needs_a_real_reason(api, world):
    r = await api.post(
        f"/api/lots/{world.lot_id}/override", headers=ADMIN,
        json={"factory_id": world.factory_id, "reason": " x "},
    )
    assert r.status_code == 422
    assert fields(r) == {"reason": "Reason must be at least 3 characters"}


async def test_text_fields_have_a_ceiling(api):
    r = await api.post(
        "/api/me/register", headers=who("v-10"),
        json={"role": "buyer", "display_name": "x" * 81},
    )
    assert fields(r) == {"display_name": "Name must be at most 80 characters"}


async def test_names_are_trimmed(api):
    r = await api.post(
        "/api/me/register", headers=who("v-11"), json={"role": "buyer", "display_name": "  Bilal  "}
    )
    assert r.json()["display_name"] == "Bilal"
