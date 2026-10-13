# voice

ADK voice agent (Python 3.12, FastAPI, Gemini Live bidi streaming, Twilio Media Streams).

```
pip install -e ".[dev]"
uvicorn app.main:app --reload --port 8001   # GET /health
pytest
python ../scripts/check_no_db_in_voice.py    # must pass: no database imports in this project
```

Routes: `POST /twilio/voice`, `WS /twilio/media`, `WS /browser`.
One agent, `intake_agent`, four tools (`create_lot`, `get_quote`, `escalate_to_human`, `record_confirmation`) that call the API with a Google ID token. This service never imports Firestore or any database client and never takes farmer identity from the model.
