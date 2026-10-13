import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    api_base_url: str = os.getenv("API_BASE_URL", "http://localhost:8000")
    api_auth_disabled: bool = os.getenv("API_AUTH_DISABLED", "false").lower() == "true"
    twilio_auth_token: str = os.getenv("TWILIO_AUTH_TOKEN", "")
    public_base_url: str = os.getenv("PUBLIC_BASE_URL", "")


def get_settings() -> Settings:
    return Settings()
