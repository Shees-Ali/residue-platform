# Decision log

Append only. Mark superseded entries as `SUPERSEDED by <date> <title>`; never delete.

## 2026-10-13 - Monorepo with three projects
web/ (React), api/ (FastAPI), voice/ (ADK) plus deploy/, seed/, memory/. Reason: one repo lets Pydantic models drive the OpenAPI spec and the typed web client; matches the plan.

## 2026-10-13 - Voice service never touches the database
voice/ calls the API over HTTPS with a Google ID token and imports no Firestore or DB client. Enforced by `scripts/check_no_db_in_voice.py` in CI. Reason: the API alone decides whether money moves.

## 2026-10-13 - Agent routes expose four tools only; identity comes from the call record
`/api/agent/*` has create lot, get quote, escalate, record confirmation. Request models carry a `call_id` and never a farmer id; the API resolves the farmer from the call record. Writes require an `Idempotency-Key` header. Reason: the model controls request fields, so it must not control identity.

## 2026-10-13 - Plan says quote_price, scaffold prompt says get_quote
Used `get_quote` (scaffold prompt wins; it is the later, more specific instruction). Rename later if desired.

## 2026-10-13 - Tests-first uses a `tdd` pytest marker
The failing tests for revenue_share, ledger check, offer expiry and factory scoring are marked `tdd`. CI runs `-m "not tdd"` as the blocking gate and `-m tdd` as a non-blocking job. Reason: a red baseline hides real regressions. Remove the marker per module when its implementation lands. Rejected: xfail (silently passes when fixed unnoticed).

## 2026-10-13 - Money as integer minor units, shares as basis points
Revenue split and ledger use integers (paisa, bps) so splits sum to exactly 10000 bps. Rejected: floats.

## 2026-10-13 - Stories not marked test-first for UI and voice
Per the plan, UI and voice agent skip tests-first; only health/smoke tests exist.

## 2026-10-13 - API Cloud Run ingress (OPEN)
Requirement: voice service account gets `run.invoker` on the API only. Browser dashboards cannot present a Cloud Run IAM token, so the deploy script defaults to `--allow-unauthenticated` with app-level auth (Firebase / Google ID token verification), and still grants the voice SA invoker. Set `API_PUBLIC=false` to make the API IAM-only (dashboards then need a proxy). To be decided before go-live.

## 2026-10-13 - Python 3.12 pinned; audioop
Voice audio conversion will use `audioop`, present in 3.12 (removed in 3.13). Local machine has 3.13; use 3.12 (Docker/CI) or add `audioop-lts`. Decide when implementing the audio path.

## 2026-10-13 - Agent-route contract tested via OpenAPI, not app.routes
Newer FastAPI wraps included routers in `_IncludedRouter`, so `app.routes` has no `.path`. `test_agent_contract.py` reads `app.openapi()["paths"]` instead.

## 2026-10-13 - Web: Tailwind v3, openapi-fetch, committed generated schema
Tailwind 3.4 (stable PostCSS setup) over v4. `openapi-fetch` pairs with `openapi-typescript` for the typed client. `web/openapi.json` and `src/api/schema.d.ts` are committed so the web builds without running the API; regenerate with `npm run gen:api` after API changes.

## 2026-10-14 - No Makefile; plain Python and npm commands
Dropped the root Makefile so contributors need nothing beyond Python and Node (make is an extra install, especially on Windows). `api/start.py` and `voice/start.py` run uvicorn with reload (ports 8000/8001, override with `PORT`); web uses `npm run dev`. Tests, lint and deploy are documented as direct commands in AGENTS.md and README (deploy via `bash deploy/*.sh`). Rejected: a root orchestrator script (one terminal per service is simple enough); Taskfile/just (same extra-tool problem). Removed targets with no replacement: `seed` (`python seed/seed.py`) and `gen-api` (`cd api && python -m scripts.export_openapi ../web/openapi.json`, then `cd web && npm run gen:api`) are now run directly.
