"""F5: a caller's own requests, in words the voice agent can say (story memory/stories/F5.md).

Reuses the dashboards' lot query, so the phone answer matches the farmer's web page.

On a real phone call the carrier vouches for the caller's number, so the caller hears full details.
On the public /phone page the number is only typed, so anyone could type someone else's: those
calls hear just the stage, the residue and the date (`details_withheld`), never places, the
factory or amounts.
"""
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.db_models.tables import Lot
from app.services.economics import gross, job_shares, payouts
from app.services.lot_views import lot_query
from app.services.lots import PKT, pickup_text

RECENT = 5  # requests read out at most; the agent asks which one if there are several

# Job state -> (stage, one plain sentence the agent says in the caller's language).
_JOB_STAGES: dict[str, tuple[str, str]] = {
    "created": ("matched", "A factory has been found; the pickup is being arranged."),
    "funded": ("finding_transporter", "The pickup is paid for; we are finding a transporter."),
    "offered": ("finding_transporter", "We are finding a transporter to collect it."),
    "accepted": (
        "transporter_coming",
        "A transporter has accepted and will come at the pickup time.",
    ),
    "picked_up": ("on_the_way", "It has been collected and is on the way to the factory."),
    "delivered": ("at_factory", "It has reached the factory and is being weighed."),
    "confirmed": (
        "awaiting_your_confirmation",
        "The factory has weighed it; we will call you to confirm the weight and amount, or you "
        "can confirm on the website.",
    ),
    "verified": ("confirmed_by_you", "You have confirmed; your payment is being released."),
    "settled": ("paid", "It is complete and your payment has been released."),
    "disputed": ("on_hold", "Payment is on hold while our team looks at your complaint."),
    "rejected": ("rejected", "The factory did not accept this load, so there is no payment."),
}
_RECEIVED = ("received", "We have your request and are matching it with a factory.")
_LOT_REJECTED = ("rejected", "This request could not be accepted.")


def stage(lot_status: str, job_state: str | None) -> tuple[str, str]:
    """(stage, sentence) for a lot and its job, if any."""
    if job_state is not None:
        return _JOB_STAGES.get(job_state, _RECEIVED)
    return _LOT_REJECTED if lot_status == "rejected" else _RECEIVED


def _rupees(paisa: int) -> float:
    return round(paisa / 100, 2)


def describe(row, *, full: bool = True) -> dict:
    """One request as the agent reads it out: never a phone, a farmer or a transporter.
    `full=False` (an unverified caller) keeps only what identifies no place and no money."""
    lot, job, _farmer, residue_label, factory_name = row
    name, sentence = stage(lot.status, job.state if job else None)
    out = {
        "lot_id": str(lot.id),
        "residue_label": residue_label,
        "reported_on": lot.created_at.astimezone(PKT).date().isoformat(),
        "stage": name,
        "status_text": sentence,
    }
    if not full:
        return {**out, "details_withheld": True}
    out |= {
        "quantity_tonnes": float(lot.quantity_tonnes),
        "village": lot.village_name,
        "district": lot.district,
        "pickup_text": (
            pickup_text(lot.pickup_from, lot.pickup_to)
            if lot.pickup_from and lot.pickup_to
            else None
        ),
    }
    if job is None:
        return out
    out["factory_name"] = factory_name
    if job.state == "rejected":  # the farmer is paid nothing for a rejected load
        out["farmer_amount_rupees"] = 0.0
        if job.rejection_reason:
            out["rejection_reason"] = job.rejection_reason
        return out
    shares = job_shares(job.farmer_share_bps)
    out["est_farmer_amount_rupees"] = _rupees(
        payouts(gross(job.est_weight_kg, job.quoted_price_per_tonne), shares)["farmer"]
    )
    if job.final_weight_kg is not None:  # the same sums settlement pays out
        out["final_weight_kg"] = job.final_weight_kg
        out["farmer_amount_rupees"] = _rupees(
            payouts(gross(job.final_weight_kg, job.quoted_price_per_tonne), shares)["farmer"]
        )
    return out


async def requests_for(db: AsyncSession, farmer_id: uuid.UUID, *, full: bool) -> list[dict]:
    """The farmer's most recent requests, newest first (id breaks a tie in time)."""
    rows = (
        await db.execute(
            lot_query()
            .where(Lot.farmer_id == farmer_id)
            .order_by(Lot.created_at.desc(), Lot.id.desc())
            .limit(RECENT)
        )
    ).all()
    return [describe(row, full=full) for row in rows]
