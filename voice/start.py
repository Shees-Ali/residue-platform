"""Local dev entrypoint: `python start.py` (auto-reload, port 8001 unless PORT is set)."""
import os

import uvicorn

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="127.0.0.1", port=int(os.getenv("PORT", "8001")), reload=True)
