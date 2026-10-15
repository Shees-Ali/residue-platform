# ruff: noqa: E501
"""M4: product details with explicit rules, order details, who sees what."""
import pytest

from tests.helpers import ADMIN, BUYER, FACTORY, OTHER_FACTORY
from tests.test_market import PRODUCT, order

CATEGORIES = ["Clean Energy", "Farming & Garden", "Building Materials", "Home & Living"]


@pytest.fixture
async def shop(api, world):
    """The test factory lists one product."""
    r = await api.post("/api/products", headers=FACTORY, json=PRODUCT)
    assert r.status_code == 201, r.text
    return r.json()


def fields(r):
    body = r.json()
    assert isinstance(body["detail"], str)
    return {e["field"]: e["message"] for e in body["errors"]}


async def post(api, **over):
    return await api.post("/api/products", headers=FACTORY, json={**PRODUCT, **over})


async def test_a_product_keeps_its_category_unit_and_description(api, world):
    r = await post(api, category="Farming & Garden", unit="per 10 kg bag", description="Rich compost.")
    assert r.status_code == 201, r.text
    p = r.json()
    assert (p["category"], p["unit"], p["description"]) == ("Farming & Garden", "per 10 kg bag", "Rich compost.")
    shelf = (await api.get("/api/products", headers=BUYER)).json()
    assert next(x for x in shelf if x["id"] == p["id"])["category"] == "Farming & Garden"


@pytest.mark.parametrize(
    "over, field, message",
    [
        ({"name": "a"}, "name", "Product name must be at least 2 characters"),
        ({"name": "x" * 121}, "name", "Product name must be at most 120 characters"),
        ({"unit_price": 99}, "unit_price", "Price must be between PKR 1 and PKR 1,000,000"),
        ({"unit_price": 100_000_001}, "unit_price", "Price must be between PKR 1 and PKR 1,000,000"),
        ({"unit_price": 12.5}, "unit_price", "Price must be between PKR 1 and PKR 1,000,000"),
        ({"stock": -1}, "stock", "Stock must be a whole number from 0 to 1,000,000"),
        ({"stock": 1_000_001}, "stock", "Stock must be a whole number from 0 to 1,000,000"),
        ({"stock": 2.5}, "stock", "Stock must be a whole number from 0 to 1,000,000"),
        ({"unit": "x"}, "unit", "Unit must be at least 2 characters"),
        ({"unit": "x" * 41}, "unit", "Unit must be at most 40 characters"),
        ({"description": "x" * 501}, "description", "Description must be at most 500 characters"),
    ],
)
async def test_each_product_rule_names_its_field(api, world, over, field, message):
    r = await post(api, **over)
    assert r.status_code == 422
    assert fields(r)[field] == message


async def test_the_category_must_be_one_of_the_four(api, world):
    r = await post(api, category="Weapons")
    assert fields(r)["category"] == (
        "Category must be one of Clean Energy, Farming & Garden, Building Materials or Home & Living"
    )
    missing = {k: v for k, v in PRODUCT.items() if k != "category"}
    r = await api.post("/api/products", headers=FACTORY, json=missing)
    assert fields(r) == {"category": "Category is required"}


async def test_every_missing_field_is_reported_at_once(api, world):
    r = await api.post("/api/products", headers=FACTORY, json={})
    assert set(fields(r)) == {"name", "unit_price", "stock", "category", "unit"}


async def test_editing_a_product_checks_the_same_rules(api, shop):
    url = f"/api/products/{shop['id']}"
    ok = await api.patch(url, headers=FACTORY, json={"unit_price": 30_000, "stock": 4, "category": "Home & Living"})
    assert ok.status_code == 200 and ok.json()["category"] == "Home & Living"
    bad = await api.patch(url, headers=FACTORY, json={"unit_price": 5, "stock": -2, "unit": "x"})
    assert set(fields(bad)) == {"unit_price", "stock", "unit"}
    assert (await api.patch(url, headers=OTHER_FACTORY, json={"stock": 1})).status_code == 404


@pytest.mark.parametrize("quantity", [0, -1, 1001, 2.5, "two"])
async def test_an_order_quantity_is_a_whole_number_from_1_to_1000(api, shop, quantity):
    r = await order(api, shop["id"], quantity)
    assert r.status_code == 422
    assert fields(r) == {"quantity": "Quantity must be a whole number between 1 and 1000"}


async def test_an_order_names_its_product_and_says_when(api, shop):
    placed = (await order(api, shop["id"], 2)).json()
    assert placed["product_name"] == "Biomass pellets" and placed["created_at"]
    mine = (await api.get("/api/orders", headers=BUYER)).json()
    assert any(o["id"] == placed["id"] and o["product_name"] == "Biomass pellets" for o in mine)
    assert (await api.get(f"/api/orders/{placed['id']}/split", headers=ADMIN)).json()["shares_total_bps"] == 10_000


async def test_asking_for_more_than_is_in_stock_is_explained(api, shop):
    r = await order(api, shop["id"], 11)  # only 10 on the shelf
    assert r.status_code == 409
    assert "Not enough stock" in r.json()["detail"]
