import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select

from app.auth.firebase import (
    AuthUser,
    as_admin,
    as_admin_or_factory,
    as_factory,
    as_farmer,
    as_transporter,
    current_user,
)
from app.auth.owners import factory_of, transporter_of
from app.db_models.tables import Event, Farmer, Grade, Job, LedgerEntry, Lot, Photo
from app.deps import DbSession, Delivery
from app.models.delivery import (
    ConfirmIn,
    GradeIn,
    GradeOut,
    LegIn,
    PingIn,
    PingOut,
    UploadUrlIn,
    UploadUrlOut,
    VerificationCallOut,
    VerifyIn,
    VerifyOut,
)
from app.models.job import JobOfferOut, JobOut
from app.models.notifications import JobEventOut
from app.models.reports import LedgerEntryOut
from app.models.tracking import TrackOut
from app.services.delivery import (
    check_photo_path,
    check_photo_uploaded,
    check_weight,
    record_leg,
)
from app.services.dispatch_store import start_dispatch
from app.services.funding import fund_job
from app.services.grading import Grader, get_grader
from app.services.inbox import commit_and_deliver
from app.services.job_flow import load_job
from app.services.job_views import Viewer, job_ladder, job_out, list_jobs
from app.services.settlement import confirm_delivery, reject_delivery
from app.services.storage import Storage, get_storage, new_photo_path
from app.services.tracking import MOVING, record_ping, track_for
from app.services.verification import record_web_answer, verification_call_for
from app.validation import FieldErrors

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


async def visible_job(db, user: AuthUser, job_id: str) -> JobOut:
    """A job the caller may see: admin all, a factory its own, a transporter its assigned ones,
    a farmer the job of their own lot."""
    if user.role not in ("admin", "factory", "transporter", "farmer"):
        raise HTTPException(403, "Forbidden")
    job = await load_job(db, job_id)
    viewer = Viewer(user.role)
    if user.role == "factory":
        if job.factory_id != (await factory_of(db, user)).id:
            raise HTTPException(404, "Unknown job")
    elif user.role == "transporter":
        carrier = await transporter_of(db, user)
        if job.transporter_id != carrier.id:
            raise HTTPException(404, "Unknown job")
        viewer = Viewer("transporter", carrier.id)
    elif user.role == "farmer":
        owner = (
            await db.execute(
                select(Farmer.user_uid).join(Lot, Lot.farmer_id == Farmer.id).where(
                    Lot.id == job.lot_id
                )
            )
        ).scalar_one_or_none()
        if owner != user.uid:
            raise HTTPException(404, "Unknown job")
    return await job_out(db, job.id, viewer)


async def own_job_as_factory(db, user: AuthUser, job_id: str) -> tuple:
    factory = await factory_of(db, user)
    job = await load_job(db, job_id, lock=True)
    if job.factory_id != factory.id:
        raise HTTPException(404, "Unknown job")
    return job, factory


async def own_job_as_transporter(db, user: AuthUser, job_id: str) -> Job:
    transporter = await transporter_of(db, user)
    job = await load_job(db, job_id, lock=True)
    if job.transporter_id != transporter.id:
        raise HTTPException(404, "Unknown job")
    return job


@router.get("", response_model=list[JobOut])
async def get_jobs_root(
    db: DbSession,
    state: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: AuthUser = Depends(current_user),
):
    scope: dict = {}
    viewer = Viewer(user.role)
    if user.role == "factory":
        scope["factory_id"] = (await factory_of(db, user)).id
    elif user.role == "transporter":
        carrier = await transporter_of(db, user)
        scope["transporter_id"] = carrier.id
        viewer = Viewer("transporter", carrier.id)
    elif user.role == "farmer":
        scope["farmer_uid"] = user.uid
    elif user.role != "admin":
        raise HTTPException(403, "Forbidden")
    return await list_jobs(db, state=state, limit=limit, offset=offset, viewer=viewer, **scope)


@router.get("/{job_id}/events", response_model=list[JobEventOut])
async def get_job_events(
    db: DbSession,
    job_id: str,
    limit: int = 100,
    user: AuthUser = Depends(current_user),
):
    """What happened to this job and who did it: what this reader may see, oldest first."""
    if not 1 <= limit <= 200:
        raise FieldErrors([("limit", "Limit must be between 1 and 200")], code="invalid_limit")
    job = await visible_job(db, user, job_id)  # 404 unless the job is theirs
    # the lot's own events (reported, matched) happened before the job existed
    query = select(Event).where(Event.lot_id == uuid.UUID(job.lot_id)).order_by(Event.created_at)
    if user.role != "admin":
        query = query.where(Event.visible_to.contains([user.role]))
    rows = (await db.execute(query.limit(limit))).scalars().all()
    return [
        JobEventOut(
            id=str(e.id), type=e.type, summary=e.summary, actor_role=e.actor_role,
            created_at=e.created_at,
        )
        for e in rows
    ]


@router.get("/{job_id}/offers", response_model=list[JobOfferOut])
async def get_job_offers(db: DbSession, job_id: str, user: AuthUser = as_admin):
    """Who was offered this job, in order, and what each did (admin)."""
    job = await load_job(db, job_id)
    return await job_ladder(db, job.id)


@router.get("/{job_id}", response_model=JobOut)
async def get_jobs_job_id(db: DbSession, job_id: str, user: AuthUser = Depends(current_user)):
    return await visible_job(db, user, job_id)


# --- FA1 ------------------------------------------------------------------------------------


@router.post("/{job_id}/fund", response_model=JobOut)
async def post_jobs_job_id_fund(
    db: DbSession, inbox: Delivery, job_id: str, user: AuthUser = as_factory
):
    """Fund escrow (simulated). Starts dispatch: the nearest eligible transporter gets an offer."""
    job, factory = await own_job_as_factory(db, user, job_id)
    await fund_job(db, job, factory, actor=user)
    out = await job_out(db, job.id, Viewer("factory"))
    await commit_and_deliver(db, inbox)
    return out


@router.post("/{job_id}/redispatch", response_model=JobOut)
async def post_jobs_job_id_redispatch(
    db: DbSession, inbox: Delivery, job_id: str, user: AuthUser = as_admin
):
    """Offer a funded job again, e.g. after approving a transporter when every one passed."""
    job = await load_job(db, job_id, lock=True)
    if job.state != "funded":
        raise HTTPException(409, "Only a funded job waiting for a transporter can be redispatched")
    if await start_dispatch(db, job) is None:
        raise HTTPException(409, "Every eligible transporter has already been asked")
    out = await job_out(db, job.id, Viewer("admin"))
    await commit_and_deliver(db, inbox)
    return out


# --- T2 -------------------------------------------------------------------------------------


@router.post("/{job_id}/photos/upload-url", response_model=UploadUrlOut)
async def post_jobs_job_id_photo_url(
    db: DbSession,
    job_id: str,
    body: UploadUrlIn,
    user: AuthUser = Depends(current_user),
    storage: Storage = Depends(get_storage),
):
    """Signed URL to upload one photo to storage; send the path back on pickup or deliver."""
    allowed = {"transporter": ("pickup", "delivery"), "factory": ("weighbridge",)}
    if body.kind not in allowed.get(user.role, ()):
        raise HTTPException(403, f"A {user.role} cannot upload a {body.kind} photo")
    await visible_job(db, user, job_id)
    path = new_photo_path(job_id, body.kind, body.content_type)
    return UploadUrlOut(
        path=path, upload_url=await storage.signed_upload_url(path, body.content_type)
    )


@router.post("/{job_id}/pickup", response_model=JobOut)
async def post_jobs_job_id_pickup(
    db: DbSession,
    inbox: Delivery,
    job_id: str,
    body: LegIn,
    user: AuthUser = as_transporter,
    storage: Storage = Depends(get_storage),
):
    """Pickup: the photo (already uploaded), the weight and where the transporter is."""
    job = await own_job_as_transporter(db, user, job_id)
    await record_leg(db, job, "pickup", user.uid, body, storage)
    out = await job_out(db, job.id, Viewer("transporter", job.transporter_id))
    await commit_and_deliver(db, inbox)
    return out


@router.post("/{job_id}/deliver", response_model=JobOut)
async def post_jobs_job_id_deliver(
    db: DbSession,
    inbox: Delivery,
    job_id: str,
    body: LegIn,
    user: AuthUser = as_transporter,
    storage: Storage = Depends(get_storage),
):
    """Delivery at the factory: the photo, the weight and where the transporter is."""
    job = await own_job_as_transporter(db, user, job_id)
    await record_leg(db, job, "delivery", user.uid, body, storage)
    out = await job_out(db, job.id, Viewer("transporter", job.transporter_id))
    await commit_and_deliver(db, inbox)
    return out


# --- FA2 ------------------------------------------------------------------------------------


@router.post("/{job_id}/grade", response_model=GradeOut)
async def post_jobs_job_id_grade(
    db: DbSession,
    job_id: str,
    body: GradeIn,
    user: AuthUser = as_factory,
    storage: Storage = Depends(get_storage),
    grader: Grader = Depends(get_grader),
):
    """AI visual estimate of the delivered lot. Never replaces the weighbridge confirmation."""
    job, _ = await own_job_as_factory(db, user, job_id)
    if job.state != "delivered":
        raise HTTPException(409, "A lot can be graded once it has been delivered")
    if body.photo_path:
        check_photo_path(str(job.id), "weighbridge", body.photo_path)
        await check_photo_uploaded(storage, body.photo_path)
        db.add(
            Photo(job_id=job.id, kind="weighbridge", storage_path=body.photo_path,
                  uploaded_by_uid=user.uid)
        )
        await db.flush()
    photos = (
        await db.execute(
            select(Photo)
            .where(Photo.job_id == job.id, Photo.kind.in_(("delivery", "weighbridge")))
            .order_by(Photo.created_at.desc())
            .limit(4)
        )
    ).scalars().all()
    if not photos:
        raise HTTPException(422, "Upload a delivery or weighbridge photo first")
    images, graded_photo = [], None
    for p in photos:  # newest first; a photo whose upload never finished is skipped
        try:
            images.append(await storage.read(p.storage_path))
        except FileNotFoundError:
            continue
        graded_photo = graded_photo or p
    if not images:
        raise HTTPException(422, "The photos were not uploaded to their URLs yet")
    grade = await grader.grade(images)
    db.add(
        Grade(
            photo_id=graded_photo.id,
            residue_code=grade.residue_type,
            moisture_band=grade.moisture_band,
            contamination_flags=grade.contamination_flags,
            confidence=grade.confidence,
        )
    )
    await db.flush()
    out = GradeOut(photo_id=str(graded_photo.id), grade=grade)
    await db.commit()
    return out


@router.post("/{job_id}/confirm", response_model=JobOut)
async def post_jobs_job_id_confirm(
    db: DbSession, inbox: Delivery, job_id: str, body: ConfirmIn, user: AuthUser = as_factory
):
    """Weigh and decide. Accept sets the final weight and pays the transporter; reject records the
    reason and applies the cost rule (transporter paid their share, the rest refunded)."""
    job, factory = await own_job_as_factory(db, user, job_id)
    if body.accept:
        if body.final_weight_kg is None:
            raise HTTPException(422, "final_weight_kg (the weighbridge weight) is required")
        check_weight(body.final_weight_kg, "final_weight_kg")
        await confirm_delivery(db, job, factory, body.final_weight_kg, actor=user)
    else:
        reason = body.reason.strip()
        if len(reason) < 3 or len(reason) > 500:
            raise FieldErrors(
                [("reason", "Give a reason of at least 3 characters (at most 500)")],
                code="invalid_reason",
            )
        await reject_delivery(db, job, factory, body.reason.strip(), actor=user)
    out = await job_out(db, job.id, Viewer("factory"))
    await commit_and_deliver(db, inbox)
    return out


# --- location tracking ------------------------------------------------------------------


@router.post("/{job_id}/location", response_model=PingOut)
async def post_jobs_job_id_location(
    db: DbSession, job_id: str, body: PingIn, user: AuthUser = as_transporter
):
    """The transporter's phone sends where it is while the job is in progress."""
    job = await own_job_as_transporter(db, user, job_id)
    if job.state not in MOVING:
        raise HTTPException(409, "Location is only shared while a job is in progress")
    recorded = await record_ping(db, job, body)
    await db.commit()
    return PingOut(recorded=recorded)


@router.get("/{job_id}/track", response_model=TrackOut)
async def get_jobs_job_id_track(
    db: DbSession, job_id: str, user: AuthUser = as_admin_or_factory
):
    """The map data for one job: farm, factory, the track and a rough arrival time."""
    job = await load_job(db, job_id)
    if user.role == "factory" and job.factory_id != (await factory_of(db, user)).id:
        raise HTTPException(404, "Unknown job")
    return await track_for(db, job)


# --- F4 on the web: the farmer answers --------------------------------------------------


@router.post("/{job_id}/verify", response_model=VerifyOut)
async def post_jobs_job_id_verify(
    db: DbSession, inbox: Delivery, job_id: str, body: VerifyIn, user: AuthUser = as_farmer
):
    """The farmer confirms the weight and payment (settles) or disputes it (freezes the money).

    The phone call does the same through /api/agent/confirmations; both end in the same code.
    """
    result = await record_web_answer(db, user.uid, job_id, body.confirmed, body.note)
    await commit_and_deliver(db, inbox)
    return VerifyOut(**result)


@router.get("/{job_id}/ledger", response_model=list[LedgerEntryOut])
async def get_jobs_job_id_ledger(db: DbSession, job_id: str, user: AuthUser = as_admin_or_factory):
    """The money movements for one job: escrow in, payouts, refunds (admin or owning factory)."""
    job = await load_job(db, job_id)
    if user.role == "factory" and job.factory_id != (await factory_of(db, user)).id:
        raise HTTPException(404, "Unknown job")
    rows = (
        await db.execute(
            select(LedgerEntry).where(LedgerEntry.job_id == job.id).order_by(LedgerEntry.created_at)
        )
    ).scalars().all()
    return [
        LedgerEntryOut(
            id=str(e.id), job_id=str(e.job_id), order_id=None, kind=e.kind, amount=e.amount,
            created_at=e.created_at,
        )
        for e in rows
    ]


# --- F4 (admin demo button; the Twilio dial-out itself belongs to the voice plan) ---------


@router.post("/{job_id}/verification-call", response_model=VerificationCallOut)
async def post_jobs_job_id_verification_call(
    db: DbSession, inbox: Delivery, job_id: str, user: AuthUser = as_admin
):
    """Open a verification call for the job's farmer. TODO(F4): the voice service dials it."""
    job = await load_job(db, job_id, lock=True)
    call = await verification_call_for(db, job)
    lot = await db.get(Lot, job.lot_id)
    farmer = await db.get(Farmer, lot.farmer_id)
    out = VerificationCallOut(
        call_id=str(call.id), job_id=str(job.id), farmer_id=str(farmer.id),
        farmer_phone=farmer.phone,
    )
    await commit_and_deliver(db, inbox)
    return out
