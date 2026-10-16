"""Start the API for the browser end-to-end tests (web: npm run e2e), on its own database and the
local Firebase emulators. Never run against anything real: it sets every switch itself.

    python -m scripts.run_e2e_api            # listens on 127.0.0.1:8010
"""
import os
import subprocess
import sys

from scripts.prepare_e2e_db import target_url

PORT = int(os.getenv("E2E_API_PORT", "8010"))


def main() -> None:
    url = target_url()
    # a separate process, so this one imports nothing from the app until the environment is set
    subprocess.run([sys.executable, "-m", "scripts.prepare_e2e_db"], check=True)
    # set before the app is imported: its settings read the environment once
    os.environ.update(
        DATABASE_URL=url,
        AUTH_DISABLED="false",
        FIREBASE_PROJECT_ID="demo-residue",
        GOOGLE_CLOUD_PROJECT="demo-residue",
        FIREBASE_AUTH_EMULATOR_HOST=os.getenv("FIREBASE_AUTH_EMULATOR_HOST", "127.0.0.1:9099"),
        FIRESTORE_EMULATOR_HOST=os.getenv("FIRESTORE_EMULATOR_HOST", "127.0.0.1:8080"),
        FIRESTORE_EVENTS="1",
        BOOTSTRAP_ADMIN_EMAILS="admin@e2e.test",
        DISPATCH_LOOP_SECONDS="0",
        OFFER_TTL_SECONDS="600",
        REQUIRE_VERIFIED_PHONE="false",
        STORAGE_BUCKET="",
    )
    os.environ.pop("K_SERVICE", None)
    import uvicorn  # noqa: PLC0415

    uvicorn.run("app.main:app", host="127.0.0.1", port=PORT, log_level="warning")


if __name__ == "__main__":
    main()
