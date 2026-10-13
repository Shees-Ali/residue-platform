"""Per-call state set by the transport layer (Twilio/browser), never by the model.

Tools read the call id from here, so the model cannot choose whose call it is acting for.
"""
from contextvars import ContextVar

current_call_id: ContextVar[str] = ContextVar("current_call_id")
