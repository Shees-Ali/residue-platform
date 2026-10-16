import logging
import re

from fastapi import FastAPI

from app import browser_routes, telnyx_routes

app = FastAPI(title="Residue Voice", version="0.1.0")

_QUERY = re.compile(r"(/telnyx/media)\?\S*")


def _redact(text: str) -> str:
    return _QUERY.sub(r"\1?<redacted>", text)


class RedactStreamTokens(logging.Filter):
    """Uvicorn logs every WebSocket handshake with its full URL; a media-stream URL's query is a
    short-lived bearer token (app/telnyx.py), so it never reaches the logs."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = _redact(record.msg)
        if isinstance(record.args, tuple):
            record.args = tuple(_redact(a) if isinstance(a, str) else a for a in record.args)
        return True


for _name in ("uvicorn.error", "uvicorn.access"):
    logging.getLogger(_name).addFilter(RedactStreamTokens())


@app.get("/health", tags=["health"])
async def health() -> dict:
    return {"status": "ok"}


app.include_router(telnyx_routes.router)
app.include_router(browser_routes.router)
