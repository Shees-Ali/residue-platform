import os
from dataclasses import dataclass, field


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default)


@dataclass(frozen=True)
class Settings:
    # default_factory reads the environment when Settings() is built, not at import time
    api_base_url: str = field(default_factory=lambda: _env("API_BASE_URL", "http://localhost:8000"))
    api_auth_disabled: bool = field(
        default_factory=lambda: _env("API_AUTH_DISABLED", "false").lower() == "true"
    )
    telnyx_api_key: str = field(default_factory=lambda: _env("TELNYX_API_KEY"))
    # Base64 Ed25519 key from Mission Control (Keys & Credentials > Public Key)
    telnyx_public_key: str = field(default_factory=lambda: _env("TELNYX_PUBLIC_KEY"))
    # Signs per-call stream URLs; the API must have the same value (it signs dialled calls)
    stream_secret: str = field(default_factory=lambda: _env("STREAM_SECRET"))
    # Public https URL of this service: Telnyx's media stream connects to its /telnyx/media
    public_base_url: str = field(
        default_factory=lambda: _env("PUBLIC_BASE_URL").rstrip("/")
    )
    # Browser mic fallback (/browser): off unless enabled; only these exact page origins.
    browser_calls_enabled: bool = field(
        default_factory=lambda: _env("BROWSER_CALLS_ENABLED", "false").lower() == "true"
    )
    browser_allowed_origins: frozenset[str] = field(
        default_factory=lambda: frozenset(
            o.strip() for o in _env("BROWSER_ALLOWED_ORIGINS").split(",") if o.strip()
        )
    )


def get_settings() -> Settings:
    return Settings()
