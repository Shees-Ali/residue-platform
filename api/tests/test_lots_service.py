from datetime import UTC, date

import pytest

from app.services.lots import (
    LotError,
    VillageRow,
    canonical_district,
    match_place,
    pickup_text,
    pickup_window,
    validate_quantity,
    validate_residue,
)

TODAY = date(2026, 10, 14)
VILLAGES = [
    VillageRow("v1", "Raiwind", 31.4, 74.4),
    VillageRow("v2", "Jallo", 31.58, 74.44),
]


def code_of(exc_info) -> str:
    return exc_info.value.code


# --- pickup window -----------------------------------------------------------


@pytest.mark.parametrize(
    ("part", "start_utc", "end_utc"),
    [("morning", 1, 7), ("afternoon", 7, 12), ("evening", 12, 15)],  # PKT = UTC+5
)
def test_pickup_parts_convert_from_pakistan_time(part, start_utc, end_utc):
    start, end = pickup_window("2026-10-15", part, today=TODAY)
    assert start.tzinfo is UTC
    assert (start.hour, end.hour) == (start_utc, end_utc)
    assert start.day == end.day == 15


def test_pickup_today_is_allowed_and_yesterday_is_not():
    assert pickup_window("2026-10-14", "evening", today=TODAY)
    with pytest.raises(LotError) as e:
        pickup_window("2026-10-13", "morning", today=TODAY)
    assert code_of(e) == "pickup_date_in_past"


def test_pickup_rejects_far_future_bad_date_and_bad_part():
    with pytest.raises(LotError) as e:
        pickup_window("2027-01-01", "morning", today=TODAY)
    assert code_of(e) == "pickup_date_too_far"
    with pytest.raises(LotError) as e:
        pickup_window("tomorrow", "morning", today=TODAY)
    assert code_of(e) == "invalid_pickup_date"
    with pytest.raises(LotError) as e:
        pickup_window("2026-10-15", "noon", today=TODAY)
    assert code_of(e) == "invalid_pickup_part"
    assert e.value.valid == ["morning", "afternoon", "evening"]


def test_pickup_part_is_case_insensitive_and_text_reads_in_pakistan_time():
    start, end = pickup_window("2026-10-15", " Morning ", today=TODAY)
    assert pickup_text(start, end) == "15 Oct 2026, 06:00 to 12:00"


# --- quantity and residue ----------------------------------------------------


@pytest.mark.parametrize("bad", [0, -1, 100.01, 1000, None, "5"])
def test_quantity_out_of_range_is_rejected(bad):
    with pytest.raises(LotError) as e:
        validate_quantity(bad)
    assert code_of(e) == "invalid_quantity"


def test_quantity_is_rounded_to_two_places():
    assert str(validate_quantity(2.5)) == "2.50"
    assert str(validate_quantity(100)) == "100.00"


def test_residue_accepts_code_in_any_case_and_lists_valid_on_failure():
    valid = {"rice_straw": "Rice straw", "wheat_straw": "Wheat straw"}
    assert validate_residue("Rice Straw", valid) == "rice_straw"
    with pytest.raises(LotError) as e:
        validate_residue("gold", valid)
    assert code_of(e) == "unknown_residue_type"
    assert e.value.valid == ["rice_straw", "wheat_straw"]


# --- places ------------------------------------------------------------------


def test_exact_village_match_ignores_case_and_uses_village_coordinates():
    m = match_place("RAIWIND", "lahore", VILLAGES)
    assert (m.match, m.village_id, m.village, m.district) == ("exact", "v1", "Raiwind", "Lahore")
    assert (m.lat, m.lon) == (31.4, 74.4)


def test_fuzzy_village_match_handles_spelling_variants():
    m = match_place("Raywind", "Lahore", VILLAGES)
    assert (m.match, m.village_id) == ("fuzzy", "v1")


def test_unknown_village_falls_back_to_the_district_centroid():
    m = match_place("Nowhere Chak 12", "Lahore", VILLAGES)
    assert (m.match, m.village_id, m.village) == ("district", None, "Nowhere Chak 12")
    assert (m.lat, m.lon) == (31.52, 74.36)


def test_unknown_district_is_an_error_with_the_valid_list():
    with pytest.raises(LotError) as e:
        match_place("Raiwind", "Atlantis", VILLAGES)
    assert code_of(e) == "unknown_district"
    assert "Lahore" in e.value.valid


def test_district_spelling_variants_resolve():
    assert canonical_district("Shaikhupura") == "Sheikhupura"
    assert canonical_district("  okara ") == "Okara"
