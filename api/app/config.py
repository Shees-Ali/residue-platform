import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")  # api/.env; real env vars win


@dataclass(frozen=True)
class Settings:
    firebase_project_id: str = os.getenv("FIREBASE_PROJECT_ID", "")
    voice_service_account: str = os.getenv("VOICE_SERVICE_ACCOUNT", "")
    api_audience: str = os.getenv("API_AUDIENCE", "")
    database_url: str = os.getenv("DATABASE_URL", "")


def get_settings() -> Settings:
    return Settings()


def bootstrap_admin_emails() -> set[str]:
    """BOOTSTRAP_ADMIN_EMAILS (comma list): a signup with a verified email in it becomes admin."""
    raw = os.getenv("BOOTSTRAP_ADMIN_EMAILS", "")
    return {e.strip().lower() for e in raw.split(",") if e.strip()}


def auth_bypass_active() -> bool:
    """Local-dev only: AUTH_DISABLED=true skips Google token checks.

    Never honoured on Cloud Run (K_SERVICE is set there), even if the variable leaks in.
    """
    return os.getenv("AUTH_DISABLED", "").lower() == "true" and not os.getenv("K_SERVICE")


def phone_verification_required() -> bool:
    """REQUIRE_VERIFIED_PHONE=true: a farmer must confirm their phone by SMS before reporting.

    Off by default while SMS is not set up (the farmer's phone is then optional and unverified).
    Always on Cloud Run (K_SERVICE is set there), whatever the variable says.
    """
    return os.getenv("REQUIRE_VERIFIED_PHONE", "").lower() == "true" or bool(os.getenv("K_SERVICE"))
