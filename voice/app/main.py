from fastapi import FastAPI

from app import browser_routes, twilio_routes

app = FastAPI(title="Residue Voice", version="0.1.0")


@app.get("/health", tags=["health"])
async def health() -> dict:
    return {"status": "ok"}


app.include_router(twilio_routes.router)
app.include_router(browser_routes.router)
