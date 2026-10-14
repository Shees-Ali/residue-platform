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
    twilio_auth_token: str = field(default_factory=lambda: _env("TWILIO_AUTH_TOKEN"))
    public_base_url: str = field(default_factory=lambda: _env("PUBLIC_BASE_URL"))


def get_settings() -> Settings:
    return Settings()
