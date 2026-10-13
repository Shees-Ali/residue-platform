from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_twilio_voice_rejects_missing_signature():
    assert client.post("/twilio/voice", data={"CallSid": "CA1"}).status_code == 403
