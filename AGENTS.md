# AGENTS.md - residue-platform

Shared rules for every coding agent and contributor.

## Project
Crop-residue marketplace demo: farmers call (Urdu, Telnyx + Gemini Live) to report residue; the API assigns a factory, dispatches transporters, runs a simulated escrow ledger and splits revenue. Synthetic data only. Plan: `memory/implementation-plan.md`.

## Layout
- `web/` React 18 + TS + Vite + Tailwind. Firebase Hosting.
- `api/` FastAPI + Pydantic v2 + Firestore. Cloud Run.
- `voice/` ADK voice agent (FastAPI, Telnyx media streams, browser mic fallback). Cloud Run.
- `deploy/` firebase.json and gcloud deploy scripts. `seed/` synthetic data. `scripts/` CI checks.
- `memory/` project memory (source of truth).

## Commands
No Makefile; only Python and Node are required.
- Setup: `pip install -e ".[dev]"` in `api/` and `voice/`; `npm install` in `web/`.
- Run: `python start.py` in `api/` (:8000) and `voice/` (:8001); `npm run dev` in `web/` (:5173).
- Test: `pytest -m "not tdd"` in `api/` (add `-m emulator` inside `firebase emulators:exec` for the Firestore tests), `pytest` in `voice/`, `npm test` in `web/`. Also `ruff check .` (api, voice), `npm run lint` (web), `npm run test:rules` and `npm run e2e` in `web/` (Firestore rules and real-browser tests on the emulators; need Java), `python scripts/check_no_db_in_voice.py`.
- Deploy: `bash deploy/deploy-api.sh|deploy-voice.sh|deploy-web.sh` (see `deploy/`). Needs gcloud and firebase CLIs logged in.

## Conventions
- Read `memory/implementation-plan.md` and the story file in `memory/stories/` before starting any story. After finishing or changing anything, update the story file (built, decided and why, open) and `memory/user-stories.md`.
- Log every decision (stack, API shape, data model, trade-offs, rejected options) in `memory/decisions.md`: dated, append only, mark superseded.
- Spec any future story in `memory/` before writing code: endpoints, data fields, done-when check, tests first.
- Tests first for: the ledger check (A3), the revenue split (FA3), offer expiry (A2), factory scoring (A1). Not for UI or voice.
- `voice/` never imports Firestore or any database client (CI enforces it). It reaches data only through the API.
- Agent routes (`/api/agent/*`) expose only: create lot, get quote, escalate, record confirmation, check status (F5). Writes need `Idempotency-Key`. Farmer identity comes from the call record, never from request fields.
- Money is integer minor units; shares are basis points summing to 10000.
- Validation first: before building any endpoint, form or field, write its constraints, error messages and feedback into the story file and `memory/validation-rules.md`, and get them confirmed by the user. Then enforce the same rule on the API (real guard) and on the web form (fast feedback), with explicit per-field errors (`{detail, errors:[{field,message,code}]}`), inline messages, a toast and a button spinner, and tests on both sides. Every typed field has a min and max length or value (`memory/validation-rules.md`, "Length limits"). Loaders show for the whole real request and never clear on a guess. See `memory/validation-rules.md`.
- Leave `TODO(<story id>)` comments for unbuilt work.
- Commit memory updates in the same commit as the code they describe. Small commits.
- Never put secrets or real farmer data in the repo, `memory/` or agent files. `.env` files stay local; `.env.example` holds placeholders.
