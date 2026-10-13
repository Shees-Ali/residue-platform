# AGENTS.md - api

Read `../AGENTS.md` first, then `../memory/implementation-plan.md` and the story file you are working on.

## Commands
- `pip install -e ".[dev]"`; `python start.py` (uvicorn --reload, :8000)
- `pytest -m "not tdd"` (green gate); `pytest -m tdd` (failing-by-design: A1, A2, A3, FA3)
- `ruff check .`; `python -m scripts.export_openapi ../web/openapi.json`

## Rules
- Routers are thin HTTP; logic lives in pure `app/services/*` modules.
- Tests first for the ledger check, revenue split, offer expiry, factory scoring. Remove the `tdd` marker when a module is implemented.
- `/api/agent/*` has exactly four routes, requires Google ID token and `Idempotency-Key` on writes, and never reads farmer identity from the body.
- Money is integer minor units; shares are basis points.
- Update the story file and `../memory/decisions.md` in the same commit.
