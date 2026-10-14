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

## 2026-10-14 - Web UI ported from the Lovable prototype; demo state first, API later
Ported the five role screens, shell, design system and demo engine from the Lovable prototype (`residue-repurpose-hub`, "FasalLoop") into `web/`, rebranded "Residue Platform". Reason: the prototype already carried polished, responsive screens for the same five roles, saving days of UI work. Adaptations: TanStack Start routes → react-router v6 (`/farmer` added as first nav item; `/` still redirects to `/market`; `/call` and `/health` kept); Tailwind v4 tokens → v3 `tailwind.config.js` + plain-CSS stylesheet (`web/src/styles/fasalloop.css`, oklch → hex, brand hexes #245C43/#D6A64D/#F8F7F2); lean shadcn subset (button, dialog, sheet, input, textarea, label, select, badge, card, table, tabs) + `tailwindcss-animate`; Google Fonts DM Sans + Manrope in `index.html`. Data: the localStorage demo engine ships as-is (`residue-demo-v1` key) so the UI is clickable now; screens swap to the typed API client story-by-story as backend stories land (Phase 1+ replaces the 6-status machine with the full job lifecycle). The demo role switcher stays as a judge-facing device and must later coexist with Firebase role claims (A2), not be replaced by them mid-demo. UI remains not test-first per the standing decision; smoke tests updated to the new screen headings. Rejected: wiring screens to the API immediately (no endpoint is implemented yet; every screen would be empty).

## 2026-10-14 - Primary store is Postgres (Cloud SQL), not Firestore
Data is relational (ledger invariants, offer ladder, four-way split, traceability), so the system of record moves to PostgreSQL. Local dev uses a Docker Postgres; Cloud SQL for Postgres at deploy time (GCP trial/billing sorted later). The API (FastAPI) is the only DB client and talks to it directly with SQLAlchemy 2 async + asyncpg, migrations with Alembic. `voice/` still never touches a database. Supersedes the "Firestore as the database" parts of `implementation-plan.md` (stack, components, running-free tables, ten-collections list). Firestore stays only for the events feed (next entry). Rejected: staying on Firestore (no FKs, awkward aggregates, integrity only in code); Firebase Data Connect (extra GraphQL layer, unclear Python server support, predefined operations make T1/settlement transactions harder, needs emulator; its generated web SDK is unused because the web reads through the API's OpenAPI client).

## 2026-10-14 - Tiny Firestore `events` collection as a refetch signal
After a Postgres commit the API writes one small doc to Firestore `events` (`{type, job_id?, at}`; no money, no personal data). Dashboards listen to it and refetch from the API. Only the API writes; signed-in users read. Replaces the live listeners on real data that the plan assumed (T1, A2, dashboards). Fallback if it is not ready: poll the API every 2-3 s. Event write failures must never fail the request (Postgres is the truth).

## 2026-10-14 - Postgres schema conventions
Money is `BIGINT` minor units with `CHECK (>= 0)`; shares are `INTEGER` bps. Statuses are `TEXT` with `CHECK (... IN (...))` (not native enums, so adding a state is a plain migration). Keys are `UUID` (server default `gen_random_uuid()`), except `users.uid` which is the Firebase uid. `timestamptz` everywhere. `ledger_entries` is append-only. T1's single winner is an atomic `UPDATE ... WHERE status='pending'` (zero rows = lost). Naming: column is `amount` (minor units); the existing `amount_cents` field in `app/models/ledger.py` is to be renamed. See `data-model.md`.

## 2026-10-14 - Optional Docker locally; external Postgres until the Google trial is live
Local dev uses the Postgres already installed on the machine (`DATABASE_URL`); an optional `api/docker-compose.yml` (Postgres only) lets anyone without Postgres run `docker compose up -d db`. Docker is not required, keeping "only Python and Node" true. Until the Google Cloud trial is running (expected within ~2 days), a free external Postgres (e.g. Neon) is the dev/demo database; then move to Cloud SQL so the demo uses Google products only. No code change between them, only `DATABASE_URL`. Rejected: Postgres in a Cloud Run container (stateless, scales to zero, data lost); a Compute Engine e2-micro VM (ops burden, VPC access). Free-tier limits change; verify before relying on them.

## 2026-10-14 - Routers get `db` and `events` dependencies now; story logic stays per story
Every stub handler takes `db: DbSession` (writes also `events: Events`) from `app/deps.py`, so stories only add logic. No endpoint behaviour changed (still 501). Exception: `farmer_id_for_call` is real because it enforces the identity rule. Without `DATABASE_URL` the session dependency returns 503, not a crash. Ledger column and model field are `amount` (renamed from `amount_cents`). Seed writes to Postgres only (JSON output removed); rows have fixed uuid5 ids so re-runs are no-ops. Rejected: implementing the story endpoints now (rules require a spec and tests first, per story).

## 2026-10-14 - Real database defaults and DB-enforced ledger rules
Column defaults are `server_default` (not ORM-only `default=`), so raw SQL, seeds and other tools insert valid rows. `ledger_entries` is made append-only by a trigger (UPDATE/DELETE raise), and a `ledger_balance` view gives the A3 per-job check (`balanced` is false mid-job by design); `services/ledger.py` stays the tested pure function. Generated migration `0001` is excluded from ruff. Rejected: ORM-only defaults (hidden coupling to Python), enforcing append-only only in app code.

## 2026-10-14 - F1: internal route group for call records
`POST /api/internal/calls` and `/{call_id}/end`, authenticated like the agent routes (Google ID token of the voice service account), called by the voice transport layer and never exposed to the model. The "exactly four routes" rule covers model-callable `/api/agent/*` only. Reason: something must link a caller's phone number to a farmer, and `voice/` cannot touch the database. Rejected: creating the call row lazily inside create_lot (trusts a phone header, misses calls without a lot).

## 2026-10-14 - F1: structured pickup window, recoverable errors, village matching
The model sends `pickup_date` (YYYY-MM-DD) and `pickup_part` (morning|afternoon|evening); the API converts to `pickup_from/to` in Pakistan time (fixed UTC+5). Invalid input returns 422 `{error, message, valid}` (handled by an exception handler for `LotError`), so the agent can ask again. Village: exact match in the district, then fuzzy (difflib 0.8), else the district centroid with `place_match="district"`; unknown district is a 422. Replaces the free-text `pickup_window` string. Rejected: free-text dates from a voice model (unreliable).

## 2026-10-14 - Auth split: voice-service auth in F1, dashboard auth later
F1 verifies Google ID tokens (email must equal `VOICE_SERVICE_ACCOUNT`, email verified, audience `API_AUDIENCE`). Firebase dashboard auth stays a 501 stub until A1/A2, the first stories with a dashboard user, so dashboard routes (and admin lot/farmer CRUD) stay 501 meanwhile. `AUTH_DISABLED=true` skips the Google check for local dev only and is ignored whenever `K_SERVICE` is set (Cloud Run). Voice has the matching `API_AUTH_DISABLED`.

## 2026-10-14 - Idempotency: stored responses, same transaction as the work
`run_idempotent` inserts the key row in the same transaction as the write and stores the response on success, so a failure rolls both back and a retry with the same key works; a replay returns the original body; same key with a different payload or route is 409; a request still in flight is 409. Concurrent duplicates wait on the unique key then replay.

## 2026-10-14 - Settings read the environment when built, not at import (voice)
`voice/app/config.py` uses `default_factory`, so flags like `API_AUTH_DISABLED` can be changed per process or per test. The API keeps import-time fields for now, with `auth_bypass_active()` reading env live.

