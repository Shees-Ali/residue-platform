"""FA3 and B1: factory products, buyer orders, stock and the four-way split."""
import uuid

import pytest
from sqlalchemy import text

from tests.helpers import ADMIN, BUYER, FACTORY, OTHER_FACTORY, scalar

PRODUCT = {"name": "Biomass pellets", "unit_price": 25_000, "stock": 10}


@pytest.fixture
async def shop(api, world):
    """The test factory lists one product."""
    r = await api.post("/api/products", headers=FACTORY, json=PRODUCT)
    assert r.status_code == 201, r.text
    return r.json()


async def ids(api, path, headers):
    """The ids in a list endpoint's response."""
    return [row["id"] for row in (await api.get(path, headers=headers)).json()]


async def stock(api, product_id):
    return await scalar(api, "SELECT stock FROM products WHERE id = :p", p=uuid.UUID(product_id))


async def order(api, product_id, quantity, headers=BUYER):
    return await api.post(
        "/api/orders", headers=headers, json={"product_id": product_id, "quantity": quantity}
    )


# --- FA3: products and the split ----------------------------------------------------------


async def test_a_factory_lists_products_and_buyers_see_them(api, shop):
    assert (shop["name"], shop["unit_price"], shop["stock"], shop["active"]) == (
        "Biomass pellets", 25_000, 10, True,
    )
    mine = (await api.get("/api/products", headers=FACTORY)).json()
    assert [p["id"] for p in mine] == [shop["id"]]
    market = (await api.get("/api/products", headers=BUYER)).json()
    assert shop["id"] in [p["id"] for p in market]
    assert next(p for p in market if p["id"] == shop["id"])["factory_name"] == "Test Factory"


async def test_only_a_factory_manages_its_own_products(api, shop):
    assert (await api.post("/api/products", headers=BUYER, json=PRODUCT)).status_code == 403
    url = f"/api/products/{shop['id']}"
    assert (await api.patch(url, headers=BUYER, json={"stock": 1})).status_code == 403
    assert (await api.patch(url, headers=OTHER_FACTORY, json={"stock": 1})).status_code == 404
    assert (await api.patch("/api/products/nope", headers=FACTORY, json={})).status_code == 404
    bad = await api.post("/api/products", headers=FACTORY, json={**PRODUCT, "unit_price": 0})
    assert bad.status_code == 422


async def test_a_factory_can_restock_reprice_and_hide_a_product(api, shop):
    url = f"/api/products/{shop['id']}"
    r = await api.patch(url, headers=FACTORY, json={"stock": 50, "unit_price": 30_000})
    assert (r.json()["stock"], r.json()["unit_price"]) == (50, 30_000)
    await api.patch(url, headers=FACTORY, json={"active": False})
    assert shop["id"] not in await ids(api, "/api/products", BUYER)
    assert shop["id"] in await ids(api, "/api/products", FACTORY)


async def test_a_sale_is_split_four_ways_and_adds_up_to_one_hundred_percent(api, shop):
    placed = await order(api, shop["id"], 3)
    assert placed.status_code == 201, placed.text
    body = placed.json()
    assert body["total"] == 75_000 and body["status"] == "paid"
    assert [(s["party"], s["share_bps"], s["amount"]) for s in body["splits"]] == [
        ("farmer", 5000, 37_500),
        ("factory", 3000, 22_500),
        ("ngo", 500, 3_750),
        ("platform", 1500, 11_250),
    ]
    assert body["shares_total_bps"] == 10_000 and body["amounts_total"] == body["total"]
    again = (await api.get(f"/api/orders/{body['id']}/split", headers=BUYER)).json()
    assert again == body


async def test_split_remainders_still_add_up_exactly(api, shop):
    r = await api.post("/api/products", headers=FACTORY,
                       json={"name": "Odd price", "unit_price": 1_001, "stock": 5})
    body = (await order(api, r.json()["id"], 3)).json()  # total 3003 does not divide evenly
    assert body["total"] == 3_003 and body["amounts_total"] == 3_003


# --- B1: orders, stock, ledger -----------------------------------------------------------


async def test_an_order_reduces_stock_and_writes_a_balanced_ledger(api, shop):
    placed = (await order(api, shop["id"], 4)).json()
    assert await stock(api, shop["id"]) == 6
    rows = await api.session.execute(
        text("SELECT kind, amount FROM ledger_entries WHERE order_id = :o ORDER BY kind"),
        {"o": uuid.UUID(placed["id"])},
    )
    ledger = {r.kind: r.amount for r in rows}
    assert ledger == {
        "escrow_in": 100_000,
        "release_farmer": 50_000,
        "release_factory": 30_000,
        "release_ngo": 5_000,
        "platform_fee": 15_000,
    }
    report = (await api.get("/api/ledger/check", headers=ADMIN)).json()
    assert report["balanced"] and report["orders_checked"] == 1


async def test_you_cannot_buy_more_than_is_in_stock_and_stock_never_goes_negative(api, shop):
    assert (await order(api, shop["id"], 10)).status_code == 201  # the last ten
    assert (await order(api, shop["id"], 1)).status_code == 409
    assert await stock(api, shop["id"]) == 0
    assert shop["id"] not in await ids(api, "/api/products", BUYER)  # sold out: off the shelf


async def test_order_validation_and_who_may_order(api, shop):
    assert (await order(api, shop["id"], 0)).status_code == 422
    assert (await order(api, str(uuid.uuid4()), 1)).status_code == 404
    assert (await order(api, "not-a-uuid", 1)).status_code == 404
    assert (await order(api, shop["id"], 1, headers=FACTORY)).status_code == 403
    await api.patch(f"/api/products/{shop['id']}", headers=FACTORY, json={"active": False})
    assert (await order(api, shop["id"], 1)).status_code == 409  # not for sale


async def test_orders_are_visible_to_the_buyer_the_factory_and_the_admin_only(api, shop):
    placed = (await order(api, shop["id"], 1)).json()
    assert await ids(api, "/api/orders", BUYER) == [placed["id"]]
    assert await ids(api, "/api/orders", FACTORY) == [placed["id"]]
    assert (await api.get("/api/orders", headers=OTHER_FACTORY)).json() == []
    assert len((await api.get("/api/orders", headers=ADMIN)).json()) >= 1
    url = f"/api/orders/{placed['id']}/split"
    assert (await api.get(url, headers=OTHER_FACTORY)).status_code == 404
    assert (await api.get(url, headers={"X-Dev-Uid": "t-trans1"})).status_code == 403
    assert (await api.get(url, headers=FACTORY)).status_code == 200
    assert (await api.get(f"/api/orders/{uuid.uuid4()}/split", headers=ADMIN)).status_code == 404
