"""The four tools the intake agent may use. Plain functions; each calls the API.

No farmer id parameter anywhere: the API derives identity from the call record.
The call id comes from app.call_context (set by the transport), not from the model.
"""
from app.api_client import post
from app.call_context import current_call_id


async def create_lot(
    residue_type: str,
    quantity_tonnes: float,
    pickup_date: str,
    pickup_part: str,
    village: str,
    district: str,
) -> dict:
    """Save the caller's residue lot, then read the returned details back to them.

    Args:
        residue_type: one of rice_straw, wheat_straw, cotton_stalk, sugarcane_trash.
        quantity_tonnes: approximate weight in tonnes, more than 0 and at most 100.
        pickup_date: the day to collect, as YYYY-MM-DD (today or later).
        pickup_part: morning, afternoon or evening.
        village: the village name as the caller says it.
        district: Lahore, Sheikhupura, Kasur, Faisalabad or Okara.

    Returns the saved lot (residue_label, quantity_tonnes, village, district, pickup_text) to read
    back, or {error, message, valid}: tell the caller what was wrong and ask again.
    """
    call_id = current_call_id.get(None)
    if call_id is None:
        return {"error": "no_active_call", "message": "No call is in progress."}
    return await post(
        "/api/agent/lots",
        call_id,
        "create_lot",
        {
            "call_id": call_id,
            "residue_type": residue_type,
            "quantity_tonnes": quantity_tonnes,
            "pickup_date": pickup_date,
            "pickup_part": pickup_part,
            "village": village,
            "district": district,
        },
    )


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
