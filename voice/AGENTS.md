# AGENTS.md - voice

Read `../AGENTS.md` first, then `../memory/implementation-plan.md` and the story file you are working on.

## Commands
- `pip install -e ".[dev]"`; `uvicorn app.main:app --reload --port 8001`
- `pytest`; `ruff check .`; `python ../scripts/check_no_db_in_voice.py`

## Rules
- NEVER import Firestore or any database client; reach data only through the API (`app/api_client.py`).
- One agent, `intake_agent`, exactly four tools: create_lot, get_quote, escalate_to_human, record_confirmation.
- Tools take no farmer id or call id from the model; the call id comes from `app/call_context.py`.
- Writes send an Idempotency-Key. Validate the Twilio signature on `/twilio/voice`.
- Update the story file and `../memory/decisions.md` in the same commit.
