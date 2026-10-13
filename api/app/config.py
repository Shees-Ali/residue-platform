import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    firebase_project_id: str = os.getenv("FIREBASE_PROJECT_ID", "")
    voice_service_account: str = os.getenv("VOICE_SERVICE_ACCOUNT", "")
    api_audience: str = os.getenv("API_AUDIENCE", "")


def get_settings() -> Settings:
    return Settings()
