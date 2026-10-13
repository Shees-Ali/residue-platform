from app.api_client import idempotency_key


def test_key_is_stable_and_payload_sensitive():
    a = idempotency_key("c1", "create_lot", {"x": 1, "y": 2})
    assert a == idempotency_key("c1", "create_lot", {"y": 2, "x": 1})
    assert a != idempotency_key("c1", "create_lot", {"x": 2, "y": 2})
    assert a != idempotency_key("c2", "create_lot", {"x": 1, "y": 2})
