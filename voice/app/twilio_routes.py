from fastapi import APIRouter, Header, HTTPException, Request, Response, WebSocket

router = APIRouter(prefix="/twilio", tags=["twilio"])


@router.post("/voice")
async def voice(request: Request, x_twilio_signature: str | None = Header(default=None)):
    """Twilio webhook: validate signature, return TwiML that opens a media stream."""
    if not x_twilio_signature:
        raise HTTPException(status_code=403, detail="Missing Twilio signature")
    # TODO(F1): twilio.request_validator.RequestValidator(auth_token).validate(url, form, sig);
    # then return TwiML <Connect><Stream url="wss://.../twilio/media"> with a one-time token param.
    return Response(content="<Response/>", media_type="application/xml", status_code=501)


@router.websocket("/media")
async def media(ws: WebSocket):
    """Twilio Media Streams <-> ADK run_live. Verify the one-time token on `start`."""
    # TODO(F1): accept, read start event (callSid, token), set current_call_id, pump audio.
    await ws.close(code=1011)
