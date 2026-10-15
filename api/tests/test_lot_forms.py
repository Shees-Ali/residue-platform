"""F1 without the phone: a farmer or an admin reports residue through the web. Constraints:
memory/validation-rules.md, section "Report residue by form"."""
import pytest
from sqlalchemy import text

from tests.helpers import ADMIN, FARMER_ESTIMATE, scalar, tomorrow

FARMER_PHONE = "+923008880099"
QUANTITY_HELP = "Quantity must be more than 0 and at most 100 tonnes"


def who(uid, phone=None):
    h = {"X-Dev-Uid": uid}
    if phone:
        h["X-Dev-Phone"] = phone
    return h


def form(**over):
    return {
        "residue_type": "rice_straw", "quantity_tonnes": 2.5, "pickup_date": tomorrow(),
        "pickup_part": "morning", "village": "Raiwind", "district": "Lahore", **over,
    }


async def farmer(api, uid="f-web", phone=FARMER_PHONE):
    r = await api.post(
        "/api/me/register", headers=who(uid, phone),
        json={"role": "farmer", "display_name": "Fatima Bibi"},
    )
    assert r.status_code == 201 and r.json()["farmer_linked"] is True, r.text
    return who(uid, phone)


async def submit(api, headers, body, key="k-1"):
    return await api.post("/api/lots/mine", headers={**headers, "Idempotency-Key": key}, json=body)


def fields(r):
    body = r.json()
    assert isinstance(body["detail"], str)
    return {e["field"]: e["message"] for e in body["errors"]}


# --- the happy path -----------------------------------------------------------------------


async def test_a_farmer_reports_residue_and_sees_it_matched_to_a_factory(api, world):
    h = await farmer(api)
    r = await submit(api, h, form())
    assert r.status_code == 201, r.text
    lot = r.json()
    assert lot["factory_name"] == "Test Factory"
    assert (lot["village"], lot["district"], lot["place_match"]) == ("Raiwind", "Lahore", "exact")
    assert lot["residue_label"] == "Rice straw"
    assert lot["job_state"] == "created"
    assert lot["est_farmer_payout"] == FARMER_ESTIMATE  # 2.5 t at the test price, 70%
    mine = (await api.get("/api/lots", headers=h)).json()
    assert [x["id"] for x in mine] == [lot["id"]]
    assert world.lot_id not in [x["id"] for x in mine]  # another farmer lot stays hidden


async def test_the_admin_sees_the_same_lot_with_the_farmer(api, world):
    h = await farmer(api)
    lot = (await submit(api, h, form())).json()
    seen = {x["id"]: x for x in (await api.get("/api/lots", headers=ADMIN)).json()}
    assert seen[lot["id"]]["farmer_phone"] == FARMER_PHONE
    assert seen[lot["id"]]["farmer_name"] == "Fatima Bibi"
    ranking = (await api.get(f"/api/lots/{lot['id']}/ranking", headers=ADMIN)).json()
    assert ranking and ranking[0]["factory_name"] == "Test Factory"


async def test_a_farmer_who_called_before_sees_phone_and_web_lots_together(api, world):
    h = await farmer(api, "f-caller", world.farmer_phone)  # the number the voice flow used
    await submit(api, h, form())
    ids = [x["id"] for x in (await api.get("/api/lots", headers=h)).json()]
    assert len(ids) == 2 and world.lot_id in ids


async def test_a_double_submit_makes_one_lot(api, world):
    h = await farmer(api)
    first = await submit(api, h, form(), key="same")
    again = await submit(api, h, form(), key="same")
    assert again.status_code == 201 and again.json()["id"] == first.json()["id"]
    count = await scalar(
        api,
        "SELECT count(*) FROM lots l JOIN farmers f ON f.id = l.farmer_id WHERE f.phone = :p",
        p=FARMER_PHONE,
    )
    assert count == 1


async def test_the_same_key_for_different_data_is_refused(api, world):
    h = await farmer(api)
    await submit(api, h, form(), key="reuse")
    r = await submit(api, h, form(quantity_tonnes=9), key="reuse")
    assert r.status_code == 409


async def test_a_new_attempt_needs_an_idempotency_key(api, world):
    h = await farmer(api)
    assert (await api.post("/api/lots/mine", headers=h, json=form())).status_code == 400


async def test_an_unknown_village_is_accepted_and_says_the_district_centre_was_used(api, world):
    h = await farmer(api)
    lot = (await submit(api, h, form(village="Madeupville"))).json()
    assert (lot["village"], lot["place_match"]) == ("Madeupville", "district")


# --- who may submit -----------------------------------------------------------------------


async def test_an_unlinked_farmer_is_told_to_verify_their_phone(api, world, sms_required):
    await api.post(
        "/api/me/register", headers=who("f-nophone"),
        json={"role": "farmer", "display_name": "No Phone"},
    )
    r = await submit(api, who("f-nophone"), form())
    assert r.status_code == 409
    assert r.json()["detail"]["code"] == "phone_not_verified"


async def test_only_farmers_may_use_the_farmer_route(api, world):
    for headers in (ADMIN, who("dev-buyer-0")):
        assert (await submit(api, headers, form())).status_code == 403


# --- field rules, one explicit message each -----------------------------------------------


@pytest.mark.parametrize(
    "over, field, message",
    [
        ({"quantity_tonnes": 0}, "quantity_tonnes", QUANTITY_HELP),
        ({"quantity_tonnes": 100.5}, "quantity_tonnes", QUANTITY_HELP),
        ({"quantity_tonnes": 2.555}, "quantity_tonnes", "Quantity can have at most 2 decimals"),
        ({"pickup_date": "2020-01-01"}, "pickup_date", "Pickup date cannot be in the past"),
        ({"pickup_date": "2099-01-01"}, "pickup_date", "Pickup date must be within 60 days"),
        (
            {"pickup_date": "soon"},
            "pickup_date",
            "Pickup date must be a real date, like 2026-10-20",
        ),
        (
            {"pickup_part": "midnight"},
            "pickup_part",
            "Pickup time must be morning, afternoon or evening",
        ),
        ({"village": " "}, "village", "Village or area is required"),
        ({"village": "x" * 81}, "village", "Village or area must be at most 80 characters"),
    ],
)
async def test_each_rule_names_its_field(api, world, over, field, message):
    h = await farmer(api)
    r = await submit(api, h, form(**over))
    assert r.status_code == 422
    assert fields(r)[field] == message


async def test_an_unknown_district_lists_the_valid_ones(api, world):
    h = await farmer(api)
    r = await submit(api, h, form(district="Atlantis"))
    assert r.status_code == 422
    assert fields(r)["district"].startswith("District must be one of")
    assert "Lahore" in r.json()["valid"]


async def test_an_unknown_residue_is_refused(api, world):
    h = await farmer(api)
    r = await submit(api, h, form(residue_type="gold"))
    assert fields(r)["residue_type"].startswith("Residue type must be one of")


async def test_a_refused_entry_leaves_nothing_and_the_key_can_be_reused(api, world):
    h = await farmer(api)
    bad = await submit(api, h, form(pickup_date="2020-01-01"), key="retry")
    assert bad.status_code == 422
    assert await scalar(api, "SELECT count(*) FROM idempotency_keys WHERE key LIKE '%retry'") == 0
    good = await submit(api, h, form(), key="retry")
    assert good.status_code == 201


# --- admin entry --------------------------------------------------------------------------


def admin_body(**over):
    return {**form(), "farmer_phone": "03005550101", "farmer_name": "Walk-in Farmer", **over}


async def test_the_admin_adds_a_lot_for_a_new_farmer_with_a_name(api, world):
    r = await api.post("/api/lots", headers=ADMIN, json=admin_body())
    assert r.status_code == 201, r.text
    row = await api.session.execute(text("SELECT name FROM farmers WHERE phone = '+923005550101'"))
    assert row.scalar() == "Walk-in Farmer"
    lots = (await api.get("/api/lots", headers=ADMIN)).json()
    assert any(x["farmer_phone"] == "+923005550101" for x in lots)


async def test_admin_entry_reports_each_bad_field(api, world):
    r = await api.post(
        "/api/lots", headers=ADMIN,
        json=admin_body(farmer_phone="call me", quantity_tonnes=0),
    )
    assert r.status_code == 422
    f = fields(r)
    assert f["farmer_phone"] == "Phone must include the country code, like +923001234567"
    assert f["quantity_tonnes"] == QUANTITY_HELP


async def test_admin_entry_with_a_bad_value_leaves_no_lot(api, world):
    before = await scalar(api, "SELECT count(*) FROM lots")
    r = await api.post("/api/lots", headers=ADMIN, json=admin_body(pickup_date="2020-01-01"))
    assert fields(r) == {"pickup_date": "Pickup date cannot be in the past"}
    assert await scalar(api, "SELECT count(*) FROM lots") == before


# --- lookups ------------------------------------------------------------------------------


async def test_the_forms_get_their_lists_from_the_api(api, world):
    h = await farmer(api)
    types = {t["code"]: t["label"] for t in (await api.get("/api/residue-types", headers=h)).json()}
    assert types["rice_straw"] == "Rice straw"
    assert "Lahore" in (await api.get("/api/districts", headers=h)).json()
    villages = (await api.get("/api/villages?district=lahore", headers=h)).json()
    assert villages and {v["district"] for v in villages} == {"Lahore"}


async def test_village_lookup_checks_the_district(api, world):
    h = await farmer(api)
    bad = await api.get("/api/villages?district=Atlantis", headers=h)
    assert bad.status_code == 422 and "district" in fields(bad)
    missing = await api.get("/api/villages", headers=h)
    assert missing.status_code == 422
    assert fields(missing) == {"district": "District is required"}


# --- link a phone later -------------------------------------------------------------------


async def test_an_unlinked_farmer_can_verify_their_phone_later(api, world, sms_required):
    await api.post(
        "/api/me/register", headers=who("f-late"),
        json={"role": "farmer", "display_name": "Late Verifier"},
    )
    r = await api.post("/api/me/link-phone", headers=who("f-late", "+923007770077"))
    assert r.status_code == 200 and r.json()["farmer_linked"] is True
    assert (await submit(api, who("f-late", "+923007770077"), form())).status_code == 201
    again = await api.post("/api/me/link-phone", headers=who("f-late", "+923007770077"))
    assert again.status_code == 200  # safe to repeat


async def test_linking_needs_a_verified_phone_on_the_token(api, world):
    await api.post(
        "/api/me/register", headers=who("f-nocode"),
        json={"role": "farmer", "display_name": "No Code"},
    )
    r = await api.post("/api/me/link-phone", headers=who("f-nocode"))
    assert r.status_code == 422
    assert fields(r) == {"phone": "Verify your phone number to continue"}


async def test_a_phone_that_belongs_to_another_login_cannot_be_linked(api, world):
    await farmer(api, "f-first", "+923007770088")
    await api.post(
        "/api/me/register", headers=who("f-second"),
        json={"role": "farmer", "display_name": "Second One"},
    )
    r = await api.post("/api/me/link-phone", headers=who("f-second", "+923007770088"))
    assert r.status_code == 409
    assert fields(r) == {"phone": "That phone number is already linked to another account"}


async def test_only_farmers_can_link_a_phone(api, world):
    r = await api.post("/api/me/link-phone", headers=who("dev-buyer-0", "+923007770099"))
    assert r.status_code == 403
