"""The Auth emulator's unsigned tokens are accepted only in a test setup, never on Cloud Run."""
import base64
import json
import time

import pytest

from app.auth import firebase

PROJECT = "demo-residue"


def token(**over) -> str:
    claims = {
        "iss": f"https://securetoken.google.com/{PROJECT}", "aud": PROJECT, "sub": "uid-1",
        "user_id": "uid-1", "email": "a@x.pk", "email_verified": True,
        "exp": time.time() + 600, **over,
    }
    part = lambda d: base64.urlsafe_b64encode(json.dumps(d).encode()).decode().rstrip("=")  # noqa: E731
    return f"{part({'alg': 'none', 'typ': 'JWT'})}.{part(claims)}."


def test_a_well_formed_emulator_token_is_read():
    assert firebase._decode_emulator_token(token(), PROJECT)["email"] == "a@x.pk"


@pytest.mark.parametrize(
    "bad, message",
    [
        (token(aud="another-project"), "wrong audience"),
        (token(iss="https://evil.example/demo-residue"), "wrong issuer"),
        (token(exp=time.time() - 5), "expired"),
        ("not-a-token", "Malformed"),
        ("a.b.c", "Malformed"),
    ],
)
def test_a_bad_emulator_token_is_refused(bad, message):
    with pytest.raises(ValueError, match=message):
        firebase._decode_emulator_token(bad, PROJECT)


def test_emulator_tokens_count_only_when_the_emulator_is_configured(monkeypatch):
    monkeypatch.delenv("FIREBASE_AUTH_EMULATOR_HOST", raising=False)
    monkeypatch.delenv("K_SERVICE", raising=False)
    assert firebase.emulator_auth_active() is False
    monkeypatch.setenv("FIREBASE_AUTH_EMULATOR_HOST", "127.0.0.1:9099")
    assert firebase.emulator_auth_active() is True


def test_cloud_run_never_accepts_an_unsigned_token(monkeypatch):
    monkeypatch.setenv("FIREBASE_AUTH_EMULATOR_HOST", "127.0.0.1:9099")
    monkeypatch.setenv("K_SERVICE", "residue-api")
    assert firebase.emulator_auth_active() is False


def test_verify_uses_the_emulator_reader_only_in_a_test_setup(monkeypatch):
    monkeypatch.setenv("FIREBASE_AUTH_EMULATOR_HOST", "127.0.0.1:9099")
    monkeypatch.delenv("K_SERVICE", raising=False)
    assert firebase._verify(token(), PROJECT)["sub"] == "uid-1"
    monkeypatch.setenv("K_SERVICE", "residue-api")
    with pytest.raises(ValueError):  # the real verifier rejects an unsigned token
        firebase._verify(token(), PROJECT)
