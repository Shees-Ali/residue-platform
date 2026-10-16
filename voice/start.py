"""Local dev entrypoint: `python start.py` (auto-reload, port 8001 unless PORT is set).

Loads `.env` from this folder when present (keys never go in the repo).
"""
import os
from pathlib import Path

import uvicorn

if __name__ == "__main__":
    env_file = Path(__file__).with_name(".env")
    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=int(os.getenv("PORT", "8001")),
        reload=True,
        env_file=env_file if env_file.exists() else None,
    )
