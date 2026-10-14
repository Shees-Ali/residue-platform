"""Where money moves for a job. Everything goes through `job_flow.transition` first, so a lost
race writes nothing, and every amount comes from `economics` so quote and ledger agree.

  confirm   delivered -> confirmed   escrow adjusted to the weighbridge weight, transporter paid
  settle    confirmed -> settled     farmer paid and platform fee taken after the farmer says yes
  dispute   confirmed -> disputed    nothing else moves; the held amount stays in escrow
  reject    delivered -> rejected    transporter paid their estimated share, the rest refunded
"""
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.db_models.tables import Factory, Job, Lot, Transporter
from app.services.economics import gross, job_shares, payouts
from app.services.job_flow import add_ledger, ledger_totals, transition


def _now(now: datetime | None) -> datetime:
    return now or datetime.now(UTC)


async def _transporter_uid(db: AsyncSession, job: Job) -> str | None:
    transporter = await db.get(Transporter, job.transporter_id)
    return transporter.user_uid if transporter else None


async def confirm_delivery(
    db: AsyncSession, job: Job, factory: Factory, final_weight_kg: int, now: datetime | None = None
) -> dict[str, int]:
    """Factory confirms the weighbridge weight. Returns the payouts for the final weight."""
    await transition(
        db, job.id, "delivered", "confirmed", final_weight_kg=final_weight_kg,
        confirmed_at=_now(now),
    )
    final_gross = gross(final_weight_kg, job.quoted_price_per_tonne)
    held = (await ledger_totals(db, job.id)).get("escrow_in", 0)
    if final_gross > held:  # heavier than estimated: the factory tops up escrow (simulated)
        await add_ledger(db, job.id, "escrow_in", final_gross - held, factory.user_uid)
    elif final_gross < held:  # lighter: the difference goes back to the factory
        await add_ledger(db, job.id, "refund", held - final_gross, factory.user_uid)
    parts = payouts(final_gross, job_shares(job.farmer_share_bps))
    await add_ledger(
        db, job.id, "release_transporter", parts["transporter"], await _transporter_uid(db, job)
    )
    return parts


async def reject_delivery(
    db: AsyncSession, job: Job, factory: Factory, reason: str, now: datetime | None = None
) -> None:
    """Pre-agreed cost rule: the transporter still gets their estimated share, the factory gets
    the rest of escrow back, the farmer gets nothing, and the lot is marked rejected."""
    await transition(db, job.id, "delivered", "rejected", rejection_reason=reason)
    estimate = gross(job.est_weight_kg, job.quoted_price_per_tonne)
    held = (await ledger_totals(db, job.id)).get("escrow_in", 0)
    haul = min(payouts(estimate, job_shares(job.farmer_share_bps))["transporter"], held)
    await add_ledger(db, job.id, "release_transporter", haul, await _transporter_uid(db, job))
    await add_ledger(db, job.id, "refund", held - haul, factory.user_uid)
    lot = await db.get(Lot, job.lot_id)
    lot.status = "rejected"
    await db.flush()


async def settle_verified(
    db: AsyncSession, job: Job, now: datetime | None = None
) -> dict[str, int]:
    """The farmer confirmed: release their share and take the platform fee."""
    stamp = _now(now)
    await transition(db, job.id, "confirmed", "settled", verified_at=stamp, settled_at=stamp)
    final_gross = gross(job.final_weight_kg, job.quoted_price_per_tonne)
    parts = payouts(final_gross, job_shares(job.farmer_share_bps))
    await add_ledger(db, job.id, "release_farmer", parts["farmer"], None)
    await add_ledger(db, job.id, "platform_fee", parts["platform"], None)
    return parts


async def dispute(db: AsyncSession, job: Job) -> None:
    """The farmer says no: freeze. The farmer share and fee stay in escrow for an admin."""
    await transition(db, job.id, "confirmed", "disputed")
