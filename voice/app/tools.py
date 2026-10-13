"""The four tools the intake agent may use. Plain functions; each calls the API.

No farmer id parameter anywhere: the API derives identity from the call record.
The call id comes from app.call_context (set by the transport), not from the model.
"""


async def create_lot(
    residue_type: str, quantity_tonnes: float, pickup_window: str, village: str, district: str
) -> dict:
    """Create a residue lot for the caller and return its details to read back."""
    # TODO(F1)
    raise NotImplementedError


async def get_quote(lot_id: str) -> dict:
    """Return price per tonne, payment timing and revenue share for the lot."""
    # TODO(F2)
    raise NotImplementedError


async def escalate_to_human(summary: str) -> dict:
    """Hand the call to a person; the transcript and summary go to the admin queue."""
    # TODO(F3)
    raise NotImplementedError


async def record_confirmation(job_id: str, confirmed: bool, note: str = "") -> dict:
    """Record the farmer's yes or dispute on weight and payment."""
    # TODO(F4)
    raise NotImplementedError


TOOLS = [create_lot, get_quote, escalate_to_human, record_confirmation]
