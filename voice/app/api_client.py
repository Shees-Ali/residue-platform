"""HTTPS client for the API. The only way this service touches data."""
import hashlib
import json


def id_token_headers() -> dict[str, str]:
    """Google ID token (audience = API URL) for the voice service account."""
    # TODO(F1): google.oauth2.id_token.fetch_id_token(Request(), audience=api_base_url);
    # skip when settings.api_auth_disabled (local dev only).
    raise NotImplementedError


def idempotency_key(call_id: str, tool: str, payload: dict) -> str:
    """Stable per (call, tool, payload) so retries by the model do not duplicate writes."""
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:16]
    return f"{call_id}:{tool}:{digest}"


async def post(path: str, call_id: str, tool: str, payload: dict, *, write: bool = True) -> dict:
    # TODO(F1): httpx POST {api_base_url}{path} with id_token_headers() and, for writes,
    # an Idempotency-Key header from idempotency_key().
    raise NotImplementedError
