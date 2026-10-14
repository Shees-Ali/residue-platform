from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.routers import agent, dispatch, internal, jobs, ledger, lots, offers, orders, products
from app.services.lots import LotError

app = FastAPI(title="Residue API", version="0.1.0")


@app.exception_handler(LotError)
async def lot_error_handler(_: Request, exc: LotError) -> JSONResponse:
    """A fixable input problem: tell the agent what was wrong and which values are valid."""
    return JSONResponse(
        status_code=422,
        content={"error": exc.code, "message": exc.message, "valid": exc.valid},
    )


@app.get("/health", tags=["health"])
async def health() -> dict:
    return {"status": "ok"}


for r in (lots, jobs, offers, ledger, products, orders, dispatch, agent, internal):
    app.include_router(r.router)
