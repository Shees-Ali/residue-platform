# FA1. Fund escrow for assigned lots

**Status:** backend done (factory UI todo)

## Spec
As a factory, I see lots assigned to me and fund escrow so dispatch can start.

**Build:** the dashboard lists jobs by state, and "fund escrow" writes an escrow-in ledger entry (simulated in the demo).

## Acceptance criteria
- Done when: a job cannot be offered to transporters until it is funded.

## Tests to write first
- Not test-first (UI / voice agent change too fast); add tests once the shape settles.

## Code TODO markers
- Search the repo for `TODO(FA1)`.

## Built so far

- 2026-10-14 backend: `GET /api/jobs` (role-scoped), `/{id}`, `POST /{id}/fund` (owning factory): `escrow_in`, `funded`, then the first offer. No offer exists before funding. Tests in `test_dispatch_flow.py`.

- 2026-10-13 scaffold: POST /api/ledger/escrow stub.
- 2026-10-13 scaffold: /factory page placeholder.

## Decisions
- None yet. Log repo-wide decisions in `../decisions.md`.

## Open
- Factory dashboard UI. Funding is simulated; no real payment partner.
