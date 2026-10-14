# Data model (PostgreSQL)

Decisions: see `decisions.md` 2026-10-14 entries. Stack: SQLAlchemy 2 async + asyncpg + Alembic, in `api/`. Local DB: Docker Postgres 16 on :5432. Firestore holds only `events`.

Conventions: UUID pks (`gen_random_uuid()`), `timestamptz`, money `BIGINT` minor units `>= 0`, shares `INTEGER` bps, statuses `TEXT` + `CHECK`. All tables have `created_at`; mutable ones also `updated_at`.

## Tables

### People and places
- `users` (uid TEXT PK = Firebase uid, role in admin|transporter|factory|buyer, display_name, phone)
- `villages` (id, name, district, lat, lon) - seeded; UNIQUE(name, district)
- `farmers` (id, phone UNIQUE, name, village_id FK, preferred_language)
- `transporters` (id, user_uid FK, phone, tier, max_tonnes, approved_at NULL, lat, lon)
- `factories` (id, user_uid FK, name, lat, lon, price_per_tonne)
- `residue_types` (code PK, label)
- `factory_residues` (factory_id FK, residue_code FK; PK both)

### Intake
- `calls` (id, twilio_call_sid UNIQUE, farmer_id FK NULL until linked, kind in intake|verification, status, transcript, summary, started_at)
- `lots` (id, farmer_id FK, call_id FK, residue_code FK, quantity_tonnes NUMERIC(10,2), pickup_from, pickup_to, village_id FK, lat, lon, status in open|assigned|rejected)
- `factory_candidates` (id, lot_id FK, factory_id FK, rank, score NUMERIC, distance_km, price_per_tonne, chosen BOOL, overridden_by_uid FK NULL, override_reason NULL; UNIQUE(lot_id, factory_id))
- `escalations` (id, call_id FK, summary, transcript, status in open|resolved, resolved_by_uid FK NULL)

### Dispatch and delivery
- `jobs` (id, lot_id FK UNIQUE, factory_id FK, transporter_id FK NULL, state in created|funded|offered|accepted|picked_up|delivered|confirmed|verified|settled|rejected|disputed, quoted_price_per_tonne, farmer_share_bps, est_weight_kg, final_weight_kg NULL, rejection_reason NULL, per-state timestamps)
- `offers` (id, job_id FK, transporter_id FK, sequence INT, expires_at, status in pending|accepted|expired|withdrawn, payout_amount; UNIQUE(job_id, sequence); partial UNIQUE (job_id) WHERE status='accepted')
- `photos` (id, job_id FK, kind in pickup|delivery|weighbridge, storage_path, uploaded_by_uid FK, weight_kg NULL)
- `grades` (id, photo_id FK, residue_code, moisture_band, contamination_flags JSONB, confidence NUMERIC, is_estimate BOOL DEFAULT true CHECK true)
- `verifications` (id, job_id FK, call_id FK, confirmed BOOL, note)

### Money
- `ledger_entries` (id, job_id FK NULL, order_id FK NULL, kind in escrow_in|release_farmer|release_transporter|platform_fee|refund, amount BIGINT >=0, party_uid FK NULL; CHECK job_id or order_id not null). Append-only: no UPDATE/DELETE from app code.
- `products` (id, factory_id FK, name, unit_price, stock INT >=0, active)
- `orders` (id, buyer_uid FK, product_id FK, quantity INT >0, total, status)
- `sale_splits` (id, order_id FK, party in farmer|factory|ngo|platform, share_bps, amount; per order shares sum to 10000, enforced in revenue_share + test)

### Plumbing
- `idempotency_keys` (key TEXT PK, route, request_hash, status_code, response JSONB NULL while in flight, created_at) - agent writes; replays return the stored response (migration 0003)
- Impact counter: derived (`SUM(final_weight_kg)` of settled jobs), no table for now.

## Views
- `ledger_balance` per job: escrow_in vs release_farmer + release_transporter + platform_fee + refund; A3 check reads it, `services/ledger.py` stays the tested pure function.

## Firestore `events` (only Firestore use)
`events/{auto}`: `{type: "job.updated"|"offer.created"|"escalation.created"|..., job_id?, at}`. No money, no PII. API writes after commit; failures logged, never raised.

## Assumptions for the open questions (change if wrong)
1. Product-to-farmer traceability: flat configured farmer share, no `product_lots` join yet. `TODO(FA3)`.
2. NGO is a label in `sale_splits.party`, not a table.
3. Ledger invariant: both the view and the pure function.
4. Column named `amount`; rename `amount_cents` in `app/models/ledger.py` and tests.
5. One lot per job.

## Build steps (to spec per story before code)
1. `docker-compose.yml` (Postgres only) in `api/`, `DATABASE_URL` in `.env.example`; drop `FIRESTORE_EMULATOR_HOST` only if the events listener is not emulated.
2. Deps: `sqlalchemy[asyncio]`, `asyncpg`, `alembic`; keep `google-cloud-firestore` for events.
3. `app/db.py` async engine/session; `app/db_models/` SQLAlchemy tables; Alembic initial migration.
4. `seed/seed.py` writes synthetic rows to Postgres.
5. Tests: DB-backed tests use a local Postgres (skipped when `DATABASE_URL` unset); pure-function tests stay DB-free.
6. Events writer `app/services/events.py` behind an interface so tests use a fake.

## Status (2026-10-14)
Built: deps (SQLAlchemy async, asyncpg, Alembic, python-dotenv), `app/db.py` (engine/session, `async_url`, 503 when `DATABASE_URL` is unset), `app/db_models/` (21 tables), Alembic env (reads `DATABASE_URL`), `app/services/events.py` (Null/Fake/Firestore sinks, on only with `FIRESTORE_EVENTS=1`), optional `api/docker-compose.yml`, Dockerfile copies migrations.
Also built: `app/deps.py` (`DbSession`, `Events` aliases) wired into every router handler (writes also get `Events`); `farmer_id_for_call(db, call_id)` in `routers/agent.py` resolves identity from the `calls` row (404 unknown, 409 not linked to a farmer); `LedgerEntry.amount` rename (was `amount_cents`); `seed/seed.py` loads synthetic rows into Postgres idempotently (fixed uuid5 ids, `--dry-run`); tests `test_db_models.py`, `test_router_wiring.py`, `test_seed.py`.
Migrations: `0001` initial schema (autogenerated, excluded from ruff), `0002` `ledger_balance` view plus a trigger that makes `ledger_entries` append-only in the database. Applied to the local `residue` database; `alembic check` shows no drift; `python seed/seed.py` loaded the synthetic rows. Column defaults are real `server_default`s (not ORM-only), so any client can insert. DB-backed tests (skip without `DATABASE_URL`, roll back) prove: append-only ledger, balance view, one accepted offer per job, no negative money.
Open: handlers are still 501 stubs, each story implements its own (F1 first: lot insert, call-to-farmer link, idempotency key storage); `Factory.price_per_tonne_cents` and `revenue_share(total_cents)` still use the `_cents` names (DB column is `price_per_tonne`); `web/openapi.json` not regenerated (FastAPI version drift only touches the ValidationError schema); voice tests need `google-adk` installed locally (unrelated to this work); move from local Postgres to Neon, then Cloud SQL, by changing `DATABASE_URL` only.

## F1 additions (2026-10-14)
Migration `0003` adds `request_hash`, `status_code`, `response` to `idempotency_keys`. Routes: `POST /api/internal/calls`, `POST /api/internal/calls/{id}/end` (voice service account, not model tools) and a real `POST /api/agent/lots`. Seed now has 30 named villages (`app/services/places.py`), 5 districts. DB-backed route tests use a session in savepoint mode so route commits roll back at test end.
