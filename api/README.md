# api

FastAPI backend (Python 3.12, Pydantic v2, PostgreSQL via SQLAlchemy async + Alembic; Firestore only for the `events` feed).

```
pip install -e ".[dev]"
python start.py                              # uvicorn --reload on :8000, GET /health
pytest -m "not tdd"                          # green gate
pytest -m tdd                                # failing-by-design tests (A1, A2, A3, FA3)
ruff check .
alembic upgrade head                         # apply migrations to DATABASE_URL
python -m scripts.export_openapi ../web/openapi.json
```

Layout: `app/routers` (HTTP only), `app/services` (pure logic, tests first), `app/models`, `app/auth`.
Agent routes (`/api/agent/*`) accept only Google ID tokens from the voice service, require `Idempotency-Key`, and never take farmer identity from the body.

## Database

Postgres is the system of record (`../memory/data-model.md`). Set `DATABASE_URL` in `api/.env` (copy `.env.example`).

- Local install: `createdb residue` (or `CREATE DATABASE residue;` in psql), then `alembic upgrade head`.
- No local Postgres: `docker compose up -d db` (optional), then use `postgresql://postgres:postgres@localhost:5432/residue`.
- Hosted (Neon, later Cloud SQL): paste its connection string; nothing else changes.
- New migration after editing `app/db_models/`: `alembic revision --autogenerate -m "message"`, then review it.
- Tests that need the database skip when `DATABASE_URL` is unset.
