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
    """Tell the caller the price per tonne, their share and when they are paid, for their lot.

    Args:
        lot_id: the lot_id returned by create_lot earlier in this call.

    Returns price_per_tonne_rupees, farmer_share_percent, farmer_per_tonne_rupees,
    est_farmer_amount_rupees and payment_timing. Say these in plain words; never invent a price.
    Returns {error, message} if there is no quote yet.
    """
    call_id = current_call_id.get(None)
    if call_id is None:
        return {"error": "no_active_call", "message": "No call is in progress."}
    return await post(
        "/api/agent/quote",
        call_id,
        "get_quote",
        {"call_id": call_id, "lot_id": lot_id},
        write=False,
    )


async def escalate_to_human(summary: str) -> dict:
    """Hand the call to a person when you cannot help or the caller is upset or confused.

    Args:
        summary: one or two sentences on what the caller needs, in English, for the admin queue.

    Tell the caller a person will contact them soon.
    """
    call_id = current_call_id.get(None)
    if call_id is None:
        return {"error": "no_active_call", "message": "No call is in progress."}
    # TODO(F3): pass the running transcript once the transport layer keeps one.
    return await post(
        "/api/agent/escalations",
        call_id,
        "escalate_to_human",
        {"call_id": call_id, "summary": summary, "transcript": ""},
    )


async def record_confirmation(job_id: str, confirmed: bool, note: str = "") -> dict:
    """Record the farmer's yes or no on the weight and payment amount, on a verification call.

    Args:
        job_id: the job being verified (given to you at the start of the verification call).
        confirmed: true only if the farmer clearly agrees with the weight and the amount.
        note: if they disagree, what they said, in a few words.

    A yes releases their payout; a no freezes it and alerts an admin.
    """
    call_id = current_call_id.get(None)
    if call_id is None:
        return {"error": "no_active_call", "message": "No call is in progress."}
    return await post(
        "/api/agent/confirmations",
        call_id,
        "record_confirmation",
        {"call_id": call_id, "job_id": job_id, "confirmed": confirmed, "note": note},
    )


TOOLS = [create_lot, get_quote, escalate_to_human, record_confirmation]
