# voice

ADK voice agent (Python 3.12, FastAPI, Gemini Live bidi streaming; phone line via Telnyx Call Control).

```
pip install -e ".[dev]"
cp .env.example .env                         # then set GEMINI_API_KEY (and BROWSER_CALLS_ENABLED=true locally)
python start.py                              # uvicorn --reload on :8001, loads .env, GET /health
pytest
python ../scripts/check_no_db_in_voice.py    # must pass: no database imports in this project
```

Routes: `WS /browser` (mic fallback used by the web `/call` page; needs `BROWSER_CALLS_ENABLED=true`), `POST /telnyx/webhook` (point the Telnyx Call Control app here) and `WS /telnyx/media` (Telnyx streams call audio here). The webhook checks Telnyx's Ed25519 signature; the stream URL carries our own HMAC (`STREAM_SECRET`).
Every transport runs a call through `app/session.py` `run_call`. The browser route also streams live events for the `/call` page (transcript, Roman Urdu from `app/roman.py`, saved lot, quote); see `app/browser_routes.py`.
One agent, `intake_agent`, four tools (`create_lot`, `get_quote`, `escalate_to_human`, `record_confirmation`) that call the API with a Google ID token. This service never imports Firestore or any database client and never takes farmer identity from the model.
