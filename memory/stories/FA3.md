# FA3. List products and see the split

**Status:** backend done (factory UI todo)

## Spec
As a factory, I list finished products for sale and see how each sale is split.

**Build:** products and orders collections, and the revenue-share calculator that splits each sale among farmer, factory, NGO and platform.

## Acceptance criteria
- Done when: a test sale shows the four-way split adding to 100%.

## Tests to write first
- Revenue split always sums to 100% (`api/tests/test_revenue_share.py`) - tests first.

## Code TODO markers
- Search the repo for `TODO(FA3)`.

## Built so far

- 2026-10-14 backend: `services/revenue_share.split` (largest remainder, un-marked from tdd), `GET/POST/PATCH /api/products`, sale split 50/30/5/15 farmer/factory/NGO/platform (`SALE_SHARE_*_BPS`), `GET /api/orders/{id}/split` showing 10000 bps and amounts equal to the total.

- 2026-10-13 scaffold: services/revenue_share.py split stub (bps, integer cents); failing tests in api/tests/test_revenue_share.py; products/orders route stubs.
- 2026-10-13 scaffold: /factory page placeholder.
- 2026-10-15 web: four-way revenue split (largest-remainder, bps) ported to TS (`web/src/lib/domain/revenueShare.ts`), mirrored tests green; B1 `createOrder` in the reducer applies it and `settle` uses it for the farmer share. API side still 501.

## Decisions
- None yet. Log repo-wide decisions in `../decisions.md`.

## Open
- Farmer share of product sales is pooled (no per-farmer attribution) and the NGO is a label; both are assumptions to confirm.

- 2026-10-16 end-to-end: web: factory `My products` (list, edit, unlist) and `Orders and revenue split`; products carry category, unit and description (migration 0009). Tests: `api/tests/test_e2e_flow.py` and the web panel tests.
