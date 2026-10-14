import pytest

from app.models.factory import Factory, LotRequest
from app.services.assignment import haversine_km, rank_factories, score_factory

LOT = LotRequest(residue_type="rice_straw", lat=31.5, lon=74.3, quantity_tonnes=10)


def fac(id_, residues, lat, lon, price):
    return Factory(
        id=id_, accepted_residues=residues, lat=lat, lon=lon, price_per_tonne_cents=price
    )


def test_haversine_zero_and_known_distance():
    assert haversine_km(31.5, 74.3, 31.5, 74.3) == pytest.approx(0)
    assert haversine_km(0, 0, 0, 1) == pytest.approx(111.19, abs=0.5)


def test_factory_not_accepting_residue_is_ineligible():
    assert score_factory(fac("f", ["wheat_straw"], 31.5, 74.3, 100), LOT) is None


def test_closer_factory_scores_higher_at_equal_price():
    near = fac("n", ["rice_straw"], 31.51, 74.31, 100)
    far = fac("f", ["rice_straw"], 32.5, 75.3, 100)
    assert score_factory(near, LOT) > score_factory(far, LOT)


def test_higher_price_scores_higher_at_equal_distance():
    cheap = fac("c", ["rice_straw"], 31.6, 74.4, 100)
    rich = fac("r", ["rice_straw"], 31.6, 74.4, 200)
    assert score_factory(rich, LOT) > score_factory(cheap, LOT)


def test_rank_drops_ineligible_and_orders_best_first():
    a = fac("a", ["rice_straw"], 31.51, 74.31, 100)
    b = fac("b", ["wheat_straw"], 31.5, 74.3, 999)
    c = fac("c", ["rice_straw"], 33.0, 75.0, 100)
    assert [f.id for f in rank_factories([c, b, a], LOT)] == ["a", "c"]
