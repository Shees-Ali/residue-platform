# api

FastAPI backend (Python 3.12, Pydantic v2, Firestore AsyncClient).

```
pip install -e ".[dev]"
python start.py                              # uvicorn --reload on :8000, GET /health
pytest -m "not tdd"                          # green gate
pytest -m tdd                                # failing-by-design tests (A1, A2, A3, FA3)
ruff check .
python -m scripts.export_openapi ../web/openapi.json
```

Layout: `app/routers` (HTTP only), `app/services` (pure logic, tests first), `app/models`, `app/auth`.
Agent routes (`/api/agent/*`) accept only Google ID tokens from the voice service, require `Idempotency-Key`, and never take farmer identity from the body.
