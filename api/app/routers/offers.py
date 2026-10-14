import uuid

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.auth.firebase import AuthUser, as_transporter
from app.auth.owners import transporter_of
from app.db_models.tables import Factory, Job, Lot, Offer, Village
from app.deps import DbSession, Events
from app.models.job import JobOut
from app.models.offer_out import OfferOut
from app.services.dispatch_store import accept_offer
from app.services.job_views import job_out

router = APIRouter(prefix="/api/offers", tags=["offers"])


@router.get("", response_model=list[OfferOut])
async def get_offers_root(db: DbSession, user: AuthUser = as_transporter):
    """The signed-in transporter's offers, open ones first, with what they need to decide."""
    transporter = await transporter_of(db, user)
    rows = (
        await db.execute(
            select(Offer, Job, Lot, Factory, Village.name)
            .join(Job, Job.id == Offer.job_id)
            .join(Lot, Lot.id == Job.lot_id)
            .join(Factory, Factory.id == Job.factory_id)
            .outerjoin(Village, Village.id == Lot.village_id)
            .where(Offer.transporter_id == transporter.id)
            .order_by((Offer.status == "pending").desc(), Offer.created_at.desc())
        )
    ).all()
    return [
        OfferOut(
            id=str(o.id),
            job_id=str(j.id),
            status=o.status,
            expires_at=o.expires_at,
            payout_amount=o.payout_amount,
            est_weight_kg=j.est_weight_kg,
            residue_type=lot.residue_code,
            village=village,
            pickup_lat=lot.lat,
            pickup_lon=lot.lon,
            factory_name=f.name,
            factory_lat=f.lat,
            factory_lon=f.lon,
        )
        for o, j, lot, f, village in rows
    ]


@router.post("/{offer_id}/accept", response_model=JobOut)
async def post_offers_offer_id_accept(
    db: DbSession,
    events: Events,
    offer_id: str,
    user: AuthUser = as_transporter,
):
    """Accept before the offer expires. Exactly one caller can win; the rest get 409."""
    transporter = await transporter_of(db, user)
    try:
        key = uuid.UUID(offer_id)
    except ValueError:
        raise HTTPException(404, "Unknown offer") from None
    job_id = await accept_offer(db, key, transporter)
    out = await job_out(db, job_id)
    await db.commit()
    await events.publish("offer.updated", str(job_id))
    await events.publish("job.updated", str(job_id))
    return out
