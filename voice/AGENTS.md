# AGENTS.md - voice

Read `../AGENTS.md` first, then `../memory/implementation-plan.md` and the story file you are working on.

## Commands
- `pip install -e ".[dev]"`; `python start.py` (uvicorn --reload, :8001)
- `pytest`; `ruff check .`; `python ../scripts/check_no_db_in_voice.py`

## Rules
- NEVER import Firestore or any database client; reach data only through the API (`app/api_client.py`).
- One agent, `intake_agent`, exactly five tools: create_lot, get_quote, escalate_to_human, record_confirmation, check_status.
- Tools take no farmer id or call id from the model; the call id comes from `app/call_context.py`.
- Writes send an Idempotency-Key. Verify the Telnyx Ed25519 signature on every webhook, and the HMAC (`STREAM_SECRET`) on every media-stream URL.
- Every transport runs calls through `app/session.py` `run_call`.
- Update the story file and `../memory/decisions.md` in the same commit.
