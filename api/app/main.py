from fastapi import FastAPI

from app.routers import agent, dispatch, jobs, ledger, lots, offers, orders, products

app = FastAPI(title="Residue API", version="0.1.0")


@app.get("/health", tags=["health"])
async def health() -> dict:
    return {"status": "ok"}


for r in (lots, jobs, offers, ledger, products, orders, dispatch, agent):
    app.include_router(r.router)
