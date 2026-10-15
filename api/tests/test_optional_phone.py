"""While SMS verification is off, a farmer's phone is optional and unverified."""
import pytest

from tests.helpers import tomorrow


def who(uid):
    return {"X-Dev-Uid": uid}


def form():
    return {
        "residue_type": "rice_straw", "quantity_tonnes": 2.5, "pickup_date": tomorrow(),
        "pickup_part": "morning", "village": "Raiwind", "district": "Lahore",
    }


async def submit(api, headers):
    return await api.post(
        "/api/lots/mine", headers={**headers, "Idempotency-Key": "k-" + headers["X-Dev-Uid"]},
        json=form(),
    )


async def test_a_farmer_can_sign_up_and_report_with_no_phone_at_all(api, world):
    h = who("opt-none")
    body = {"role": "farmer", "display_name": "No Phone"}
    r = await api.post("/api/me/register", headers=h, json=body)
    assert r.status_code == 201
    assert r.json()["farmer_linked"] is True
    assert (await submit(api, h)).status_code == 201


async def test_a_typed_phone_is_kept_when_given(api, world):
    h = who("opt-typed")
    r = await api.post(
        "/api/me/register", headers=h,
        json={"role": "farmer", "display_name": "Typed", "phone": "+923001119911"},
    )
    assert r.status_code == 201 and r.json()["phone"] == "+923001119911"
    assert (await submit(api, h)).status_code == 201


async def test_a_phone_that_is_typed_must_still_be_a_real_mobile_number(api, world):
    r = await api.post(
        "/api/me/register", headers=who("opt-bad"),
        json={"role": "farmer", "display_name": "Bad", "phone": "+92123"},
    )
    assert r.status_code == 422
    assert r.json()["errors"][0]["field"] == "phone"


async def test_an_existing_farmer_without_a_record_can_report_without_re_signing_up(
    api, world, monkeypatch
):
    # registered while SMS was required (no record), then SMS was turned off
    h = who("opt-late")
    monkeypatch.setenv("REQUIRE_VERIFIED_PHONE", "true")
    body = {"role": "farmer", "display_name": "Late"}
    await api.post("/api/me/register", headers=h, json=body)
    monkeypatch.delenv("REQUIRE_VERIFIED_PHONE")
    me = await api.get("/api/me", headers=h)
    assert me.json()["farmer_linked"] is True
    assert (await submit(api, h)).status_code == 201


async def test_cloud_run_always_requires_the_sms(api, world, monkeypatch):
    monkeypatch.setenv("K_SERVICE", "residue-api")
    # headers-only dev auth is refused there, so check the rule itself
    from app.config import phone_verification_required

    assert phone_verification_required() is True


@pytest.mark.usefixtures("sms_required")
async def test_when_required_a_typed_phone_is_not_trusted(api, world):
    h = who("opt-req")
    r = await api.post(
        "/api/me/register", headers=h,
        json={"role": "farmer", "display_name": "Req", "phone": "+923001119922"},
    )
    assert r.json()["farmer_linked"] is False
    assert r.json()["phone"] is None
