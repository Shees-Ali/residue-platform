"""PROFILE: edit my details, the admin's edit of anyone, and the admin's edit of an unfunded lot.

Rules: memory/validation-rules.md, "Edit my details, and admin edits".
"""
import uuid

import pytest

from tests.helpers import ADMIN, FACTORY, T1, fund, scalar

TRANSPORTER_BODY = {
    "role": "transporter", "display_name": "Truck Co", "phone": "+923009990001",
    "village": "Raiwind", "district": "Lahore",
}
FACTORY_BODY = {
    "role": "factory", "display_name": "New Mill", "village": "Raiwind", "district": "Lahore",
    "factory": {"name": "New Mill", "price_per_tonne": 4_000_000, "residues": ["rice_straw"]},
}


def who(uid):
    return {"X-Dev-Uid": uid}


async def signup(api, uid, body):
    r = await api.post("/api/me/register", headers=who(uid), json=body)
    assert r.status_code == 201, r.text
    return who(uid)


def fields(r):
    return {e["field"]: e["message"] for e in r.json()["errors"]}


# --- my own details ------------------------------------------------------------------------


async def test_a_factory_sees_and_edits_its_own_details(api, world):
    h = await signup(api, "pf-1", FACTORY_BODY)
    me = (await api.get("/api/me/profile", headers=h)).json()
    assert (me["district"], me["village"]) == ("Lahore", "Raiwind")  # remembered from signup
    assert me["factory"] == {
        "name": "New Mill", "price_per_tonne": 4_000_000, "residues": ["rice_straw"],
    }
    r = await api.patch(
        "/api/me/profile", headers=h,
        json={
            "display_name": "Owner Two",
            "factory": {"name": "Big Mill", "price_per_tonne": 5_000_000,
                        "residues": ["rice_straw", "wheat_straw"]},
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["display_name"] == "Owner Two"
    assert body["factory"]["name"] == "Big Mill"
    assert body["factory"]["residues"] == ["rice_straw", "wheat_straw"]


async def test_a_price_edit_does_not_change_a_job_that_was_already_assigned(api, world):
    before = await scalar(api, "SELECT quoted_price_per_tonne FROM jobs WHERE id = :j",
                          j=uuid.UUID(world.job_id))
    r = await api.patch(
        "/api/me/profile", headers=FACTORY, json={"factory": {"price_per_tonne": 50_000_000}}
    )
    assert r.status_code == 200, r.text
    after = await scalar(api, "SELECT quoted_price_per_tonne FROM jobs WHERE id = :j",
                         j=uuid.UUID(world.job_id))
    assert after == before  # the farmer was quoted the old price; it stays


async def test_the_new_price_is_used_when_the_lot_is_ranked_again(api, world):
    await api.patch(
        "/api/me/profile", headers=FACTORY, json={"factory": {"price_per_tonne": 99_999_999}}
    )
    r = await api.patch(f"/api/lots/{world.lot_id}", headers=ADMIN, json={"quantity_tonnes": 3})
    assert r.status_code == 200, r.text
    assert r.json()["quoted_price_per_tonne"] == 99_999_999
    assert r.json()["factory_name"] == "Test Factory"


async def test_a_transporter_moves_their_base_and_changes_their_phone(api, world):
    h = await signup(api, "pt-1", TRANSPORTER_BODY)
    old = await scalar(api, "SELECT lat FROM transporters WHERE user_uid = 'pt-1'")
    r = await api.patch(
        "/api/me/profile", headers=h,
        json={"phone": "+923001119911", "district": "Faisalabad", "village": "Jaranwala"},
    )
    assert r.status_code == 200, r.text  # allowed while still pending approval
    assert r.json()["status"] == "pending"
    assert (r.json()["district"], r.json()["phone"]) == ("Faisalabad", "+923001119911")
    assert await scalar(api, "SELECT lat FROM transporters WHERE user_uid = 'pt-1'") != old
    assert await scalar(api, "SELECT phone FROM transporters WHERE user_uid = 'pt-1'") == (
        "+923001119911"
    )
    assert await scalar(api, "SELECT phone FROM users WHERE uid = 'pt-1'") == "+923001119911"


async def test_changing_only_the_village_keeps_the_stored_district(api, world):
    h = await signup(api, "pt-2", TRANSPORTER_BODY)
    r = await api.patch("/api/me/profile", headers=h, json={"village": "Raiwind"})
    assert r.status_code == 200 and r.json()["district"] == "Lahore"


async def test_a_buyer_can_change_their_name_and_phone_but_has_no_base(api, world):
    h = await signup(api, "pb-1", {"role": "buyer", "display_name": "Bilal"})
    ok = await api.patch(
        "/api/me/profile", headers=h, json={"display_name": "Bilal Khan", "phone": "+923001112233"}
    )
    assert ok.status_code == 200 and ok.json()["display_name"] == "Bilal Khan"
    bad = await api.patch("/api/me/profile", headers=h, json={"district": "Lahore"})
    assert bad.status_code == 422 and "district" in fields(bad)


# --- what is refused -------------------------------------------------------------------------


@pytest.mark.parametrize(
    "body, field, message",
    [
        ({"display_name": "A"}, "display_name", "Name must be at least 2 characters"),
        ({"display_name": "x" * 81}, "display_name", "Name must be at most 80 characters"),
        ({"factory": {"name": "A"}}, "factory.name", "Factory name must be at least 2 characters"),
        (
            {"factory": {"price_per_tonne": 99}},
            "factory.price_per_tonne",
            "Price must be between PKR 1 and PKR 1,000,000 per tonne",
        ),
        (
            {"factory": {"price_per_tonne": 100_000_001}},
            "factory.price_per_tonne",
            "Price must be between PKR 1 and PKR 1,000,000 per tonne",
        ),
        ({"factory": {"residues": []}}, "factory.residues", None),
        ({"factory": {"residues": ["rice_straw", "rice_straw"]}}, "factory.residues", None),
        ({"phone": "123"}, "phone", None),
        ({"village": "x"}, "village", None),
    ],
)
async def test_a_bad_value_is_refused_with_its_field_and_message(api, world, body, field, message):
    r = await api.patch("/api/me/profile", headers=FACTORY, json=body)
    assert r.status_code == 422, r.text
    assert field in fields(r)
    if message:
        assert fields(r)[field] == message


async def test_an_unknown_residue_or_district_is_named(api, world):
    r = await api.patch(
        "/api/me/profile", headers=FACTORY, json={"factory": {"residues": ["moon_dust"]}}
    )
    assert r.status_code == 422
    assert "Unknown residue types: moon_dust" in fields(r)["factory.residues"]
    r = await api.patch(
        "/api/me/profile", headers=FACTORY, json={"district": "Narnia", "village": "Raiwind"}
    )
    assert r.status_code == 422 and "District must be one of" in fields(r)["district"]


async def test_an_empty_edit_or_an_unknown_field_is_refused(api, world):
    for body in ({}, {"display_name": None}):
        r = await api.patch("/api/me/profile", headers=FACTORY, json=body)
        assert r.status_code == 422 and fields(r)["body"] == "Change at least one field"
    r = await api.patch("/api/me/profile", headers=FACTORY, json={"email": "x@y.pk"})
    assert r.status_code == 422 and "email" in fields(r)
    r = await api.patch("/api/me/profile", headers=FACTORY, json={"role": "admin"})
    assert r.status_code == 422 and "role" in fields(r)


async def test_a_refused_edit_changes_nothing(api, world):
    before = (await api.get("/api/me/profile", headers=FACTORY)).json()
    r = await api.patch(
        "/api/me/profile", headers=FACTORY,
        json={"display_name": "Changed Name", "factory": {"residues": ["moon_dust"]}},
    )
    assert r.status_code == 422
    after = (await api.get("/api/me/profile", headers=FACTORY)).json()
    assert after["display_name"] == before["display_name"]  # the name was not half-applied


async def test_other_roles_fields_are_refused_by_field(api, world):
    h = await signup(api, "pt-3", TRANSPORTER_BODY)
    r = await api.patch("/api/me/profile", headers=h, json={"factory": {"name": "Mine"}})
    assert r.status_code == 422 and "factory" in fields(r)
    r = await api.patch("/api/me/profile", headers=h, json={"transporter": {"tier": 3}})
    assert r.status_code == 422
    assert fields(r)["transporter.tier"] == "Only an admin can change tier"


async def test_a_suspended_account_cannot_edit_but_the_admin_can(api, world):
    h = await signup(api, "pb-2", {"role": "buyer", "display_name": "Bilal"})
    await api.post("/api/users/pb-2/suspend", headers=ADMIN)
    r = await api.patch("/api/me/profile", headers=h, json={"display_name": "Sneaky"})
    assert r.status_code == 403 and "suspended" in r.json()["detail"]
    ok = await api.patch("/api/users/pb-2/profile", headers=ADMIN, json={"display_name": "Fixed"})
    assert ok.status_code == 200 and ok.json()["display_name"] == "Fixed"


async def test_a_farmer_cannot_take_a_phone_another_farmer_has(api, world):
    taken = "+923008880001"  # the farmer of the test lot
    h = await signup(api, "pf-9", {"role": "farmer", "display_name": "Other Farmer"})
    r = await api.patch("/api/me/profile", headers=h, json={"phone": taken})
    assert r.status_code == 409 and "phone" in fields(r)


async def test_a_person_without_an_account_is_told_to_sign_up(api, world):
    r = await api.get("/api/me/profile", headers=who("nobody"))
    assert r.status_code == 403


# --- the admin edits anyone --------------------------------------------------------------------


async def test_the_admin_changes_a_tier_and_the_max_load_follows(api, world):
    await signup(api, "pt-4", TRANSPORTER_BODY)
    r = await api.patch(
        "/api/users/pt-4/profile", headers=ADMIN, json={"transporter": {"tier": 3}}
    )
    assert r.status_code == 200, r.text
    assert r.json()["transporter"]["tier"] == 3 and r.json()["transporter"]["max_tonnes"] == 15
    r = await api.patch(
        "/api/users/pt-4/profile", headers=ADMIN, json={"transporter": {"max_tonnes": 4.5}}
    )
    assert r.json()["transporter"] == {"tier": 3, "max_tonnes": 4.5, "approved": False}
    both = await api.patch(
        "/api/users/pt-4/profile", headers=ADMIN, json={"transporter": {"tier": 2, "max_tonnes": 9}}
    )
    assert both.json()["transporter"]["tier"] == 2 and both.json()["transporter"]["max_tonnes"] == 9


@pytest.mark.parametrize(
    "body, field",
    [
        ({"tier": 0}, "transporter.tier"),
        ({"tier": 4}, "transporter.tier"),
        ({"max_tonnes": 0}, "transporter.max_tonnes"),
        ({"max_tonnes": 100.5}, "transporter.max_tonnes"),
    ],
)
async def test_a_tier_or_max_load_out_of_range_is_refused(api, world, body, field):
    await signup(api, "pt-5", TRANSPORTER_BODY)
    r = await api.patch("/api/users/pt-5/profile", headers=ADMIN, json={"transporter": body})
    assert r.status_code == 422 and field in fields(r)


async def test_the_admin_cannot_change_email_or_role_or_give_a_farmer_a_tier(api, world):
    await signup(api, "pf-8", {"role": "farmer", "display_name": "Farmer Eight"})
    for body in ({"email": "a@b.pk"}, {"role": "admin"}):
        r = await api.patch("/api/users/pf-8/profile", headers=ADMIN, json=body)
        assert r.status_code == 422
    r = await api.patch(
        "/api/users/pf-8/profile", headers=ADMIN, json={"transporter": {"tier": 2}}
    )
    assert r.status_code == 422 and "transporter" in fields(r)


async def test_only_the_admin_reaches_the_edit_of_anyone(api, world):
    for h in (FACTORY, T1, who("dev-buyer-0")):
        assert (await api.get("/api/users/pt-9/profile", headers=h)).status_code == 403
        assert (
            await api.patch("/api/users/pt-9/profile", headers=h, json={"display_name": "Zed"})
        ).status_code == 403
    assert (await api.get("/api/users/ghost/profile", headers=ADMIN)).status_code == 404


async def test_users_can_be_searched_by_name_or_email(api, world):
    await api.post(
        "/api/me/register", headers={"X-Dev-Uid": "pq-1", "X-Dev-Email": "zulfi@x.pk"},
        json={"role": "buyer", "display_name": "Zulfiqar Ahmad"},
    )
    for q in ("zulfiqar", "ZULFI@X", "Ahmad"):
        rows = (await api.get("/api/users", headers=ADMIN, params={"q": q})).json()
        assert [r["uid"] for r in rows] == ["pq-1"], q
    too_long = await api.get("/api/users", headers=ADMIN, params={"q": "x" * 81})
    assert too_long.status_code == 422


# --- the admin edits a lot that is not funded yet ----------------------------------------------


async def test_a_lot_edit_changes_the_job_weight_and_keeps_a_factory(api, world):
    r = await api.patch(
        f"/api/lots/{world.lot_id}", headers=ADMIN,
        json={"quantity_tonnes": 4, "pickup_part": "evening"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["quantity_tonnes"] == 4 and body["job_state"] == "created"
    assert await scalar(api, "SELECT est_weight_kg FROM jobs WHERE id = :j",
                        j=uuid.UUID(world.job_id)) == 4000
    assert await scalar(api, "SELECT count(*) FROM jobs WHERE lot_id = :l",
                        l=uuid.UUID(world.lot_id)) == 1  # updated in place, not a second job
    assert body["override_dropped"] is False
    assert body["pickup_text"] if "pickup_text" in body else True


async def test_a_lot_edit_to_another_village_moves_the_pickup_point(api, world):
    before = await scalar(api, "SELECT lat FROM lots WHERE id = :l", l=uuid.UUID(world.lot_id))
    r = await api.patch(
        f"/api/lots/{world.lot_id}", headers=ADMIN,
        json={"district": "Faisalabad", "village": "Jaranwala"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["district"] == "Faisalabad"
    after = await scalar(api, "SELECT lat FROM lots WHERE id = :l", l=uuid.UUID(world.lot_id))
    assert after != before


async def test_a_manual_factory_choice_is_dropped_and_the_response_says_so(api, world):
    ranking = (await api.get(f"/api/lots/{world.lot_id}/ranking", headers=ADMIN)).json()
    other = next(e for e in ranking if not e["chosen"])
    ok = await api.post(
        f"/api/lots/{world.lot_id}/override", headers=ADMIN,
        json={"factory_id": other["factory_id"], "reason": "Closer to the road"},
    )
    assert ok.status_code == 200, ok.text
    r = await api.patch(f"/api/lots/{world.lot_id}", headers=ADMIN, json={"quantity_tonnes": 3})
    assert r.status_code == 200 and r.json()["override_dropped"] is True
    assert r.json()["factory_name"] == "Test Factory"  # the new ranking decides again


async def test_a_funded_lot_cannot_be_edited(api, world):
    await fund(api, world)
    r = await api.patch(f"/api/lots/{world.lot_id}", headers=ADMIN, json={"quantity_tonnes": 3})
    assert r.status_code == 409
    assert r.json()["detail"] == "This lot is already funded and can no longer be changed"
    assert await scalar(api, "SELECT quantity_tonnes FROM lots WHERE id = :l",
                        l=uuid.UUID(world.lot_id)) == 2.5


@pytest.mark.parametrize(
    "body, field",
    [
        ({"quantity_tonnes": 0}, "quantity_tonnes"),
        ({"quantity_tonnes": 100.5}, "quantity_tonnes"),
        ({"pickup_date": "2020-01-01"}, "pickup_date"),
        ({"pickup_date": "not-a-date"}, "pickup_date"),
        ({"pickup_part": "midnight"}, "pickup_part"),
        ({"district": "Narnia"}, "district"),
        ({}, "body"),
        ({"residue_type": "rice_straw"}, "residue_type"),  # not editable: unknown field
    ],
)
async def test_a_lot_edit_is_validated_like_reporting_a_lot(api, world, body, field):
    r = await api.patch(f"/api/lots/{world.lot_id}", headers=ADMIN, json=body)
    assert r.status_code == 422, r.text
    assert field in fields(r)
    assert await scalar(api, "SELECT quantity_tonnes FROM lots WHERE id = :l",
                        l=uuid.UUID(world.lot_id)) == 2.5


async def test_editing_a_lot_that_does_not_exist(api, world):
    r = await api.patch(f"/api/lots/{uuid.uuid4()}", headers=ADMIN, json={"quantity_tonnes": 3})
    assert r.status_code == 404
