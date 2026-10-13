from fastapi import APIRouter, WebSocket

router = APIRouter(tags=["browser"])


@router.websocket("/browser")
async def browser(ws: WebSocket):
    """Browser mic fallback: same intake_agent, PCM over WebSocket."""
    # TODO(F1): accept, authenticate, create a call record via the API, pump audio.
    await ws.close(code=1011)
