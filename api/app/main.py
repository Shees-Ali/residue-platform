import asyncio
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.db import new_session
from app.routers import (
    agent,
    devupload,
    dispatch,
    escalations,
    impact,
    internal,
    jobs,
    ledger,
    lots,
    me,
    offers,
    orders,
    products,
    refdata,
    stats,
    tracking,
    transporters,
    users,
)
from app.services.dispatch_loop import loop_seconds, run_forever
from app.services.events import get_events
from app.services.job_states import InvalidTransition
from app.services.lots import LotError
from app.validation import FieldErrors, field_errors_handler, request_validation_handler


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Start the local dispatch loop when DISPATCH_LOOP_SECONDS is set (never on Cloud Run)."""
    task = None
    seconds = loop_seconds()
    if seconds:
        task = asyncio.create_task(run_forever(new_session, get_events(), seconds))
    yield
    if task:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


app = FastAPI(title="Residue API", version="0.1.0", lifespan=lifespan)

# The deployed web origin (Firebase Hosting). Local dev goes through the Vite proxy instead.
_origins = [o.strip() for o in os.getenv("CORS_ORIGINS", "").split(",") if o.strip()]
if _origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_origins,
        allow_methods=["*"],
        allow_headers=["Authorization", "Content-Type", "Idempotency-Key"],
    )


app.add_exception_handler(RequestValidationError, request_validation_handler)
app.add_exception_handler(FieldErrors, field_errors_handler)


@app.exception_handler(LotError)
async def lot_error_handler(_: Request, exc: LotError) -> JSONResponse:
    """A fixable input problem: tell the agent what was wrong and which values are valid."""
    return JSONResponse(
        status_code=422,
        content={"error": exc.code, "message": exc.message, "valid": exc.valid},
    )


@app.exception_handler(InvalidTransition)
async def invalid_transition_handler(_: Request, exc: InvalidTransition) -> JSONResponse:
    return JSONResponse(status_code=409, content={"detail": str(exc)})


@app.get("/health", tags=["health"])
async def health() -> dict:
    return {"status": "ok"}


for r in (
    lots, jobs, offers, ledger, products, orders, dispatch, agent, internal, escalations, impact,
    transporters, me, users, refdata, stats, tracking, devupload,
):
    app.include_router(r.router)
