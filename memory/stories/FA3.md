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

## Decisions
- None yet. Log repo-wide decisions in `../decisions.md`.

## Open
- Farmer share of product sales is pooled (no per-farmer attribution) and the NGO is a label; both are assumptions to confirm.
