from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select

from app.auth.firebase import AuthUser, as_admin, as_factory, as_transporter, current_user
from app.auth.owners import factory_of, transporter_of
from app.db_models.tables import Farmer, Grade, Job, Lot, Photo
from app.deps import DbSession, Events
from app.models.delivery import (
    ConfirmIn,
    GradeIn,
    GradeOut,
    LegIn,
    UploadUrlIn,
    UploadUrlOut,
    VerificationCallOut,
)
from app.models.job import JobOut
from app.services.delivery import check_photo_path, check_weight, record_leg
from app.services.dispatch_store import start_dispatch
from app.services.funding import fund_job
from app.services.grading import Grader, get_grader
from app.services.job_flow import load_job
from app.services.job_views import job_out, list_jobs
from app.services.settlement import confirm_delivery, reject_delivery
from app.services.storage import Storage, get_storage, new_photo_path
from app.services.verification import verification_call_for

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


async def visible_job(db, user: AuthUser, job_id: str) -> JobOut:
    """A job the caller may see: admin all, a factory its own, a transporter its assigned ones."""
    job = await load_job(db, job_id)
    if user.role == "factory":
        if job.factory_id != (await factory_of(db, user)).id:
            raise HTTPException(404, "Unknown job")
    elif user.role == "transporter":
        if job.transporter_id != (await transporter_of(db, user)).id:
            raise HTTPException(404, "Unknown job")
    elif user.role != "admin":
        raise HTTPException(403, "Forbidden")
    return await job_out(db, job.id)


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
    scope = {}
    if user.role == "factory":
        scope["factory_id"] = (await factory_of(db, user)).id
    elif user.role == "transporter":
        scope["transporter_id"] = (await transporter_of(db, user)).id
    elif user.role != "admin":
        raise HTTPException(403, "Forbidden")
    return await list_jobs(db, state=state, limit=limit, offset=offset, **scope)


@router.get("/{job_id}", response_model=JobOut)
async def get_jobs_job_id(db: DbSession, job_id: str, user: AuthUser = Depends(current_user)):
    return await visible_job(db, user, job_id)


# --- FA1 ------------------------------------------------------------------------------------


@router.post("/{job_id}/fund", response_model=JobOut)
async def post_jobs_job_id_fund(
    db: DbSession, events: Events, job_id: str, user: AuthUser = as_factory
):
    """Fund escrow (simulated). Starts dispatch: the nearest eligible transporter gets an offer."""
    job, factory = await own_job_as_factory(db, user, job_id)
    offer = await fund_job(db, job, factory)
    out = await job_out(db, job.id)
    await db.commit()
    await events.publish("ledger.updated", str(job.id))
    await events.publish("job.updated", str(job.id))
    if offer is not None:
        await events.publish("offer.created", str(job.id))
    return out


@router.post("/{job_id}/redispatch", response_model=JobOut)
async def post_jobs_job_id_redispatch(
    db: DbSession, events: Events, job_id: str, user: AuthUser = as_admin
):
    """Offer a funded job again, e.g. after approving a transporter when every one passed."""
    job = await load_job(db, job_id, lock=True)
    if job.state != "funded":
        raise HTTPException(409, "Only a funded job waiting for a transporter can be redispatched")
    if await start_dispatch(db, job) is None:
        raise HTTPException(409, "Every eligible transporter has already been asked")
    out = await job_out(db, job.id)
    await db.commit()
    await events.publish("offer.created", str(job.id))
    await events.publish("job.updated", str(job.id))
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
    path = new_photo_path(job_id, body.kind)
    return UploadUrlOut(
        path=path, upload_url=await storage.signed_upload_url(path, body.content_type)
    )


@router.post("/{job_id}/pickup", response_model=JobOut)
async def post_jobs_job_id_pickup(
    db: DbSession, events: Events, job_id: str, body: LegIn, user: AuthUser = as_transporter
):
    job = await own_job_as_transporter(db, user, job_id)
    await record_leg(db, job, "pickup", user.uid, body.photo_path, body.weight_kg)
    out = await job_out(db, job.id)
    await db.commit()
    await events.publish("job.updated", str(job.id))
    return out


@router.post("/{job_id}/deliver", response_model=JobOut)
async def post_jobs_job_id_deliver(
    db: DbSession, events: Events, job_id: str, body: LegIn, user: AuthUser = as_transporter
):
    job = await own_job_as_transporter(db, user, job_id)
    await record_leg(db, job, "delivery", user.uid, body.photo_path, body.weight_kg)
    out = await job_out(db, job.id)
    await db.commit()
    await events.publish("job.updated", str(job.id))
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
    db: DbSession, events: Events, job_id: str, body: ConfirmIn, user: AuthUser = as_factory
):
    """Weigh and decide. Accept sets the final weight and pays the transporter; reject records the
    reason and applies the cost rule (transporter paid their share, the rest refunded)."""
    job, factory = await own_job_as_factory(db, user, job_id)
    if body.accept:
        if body.final_weight_kg is None:
            raise HTTPException(422, "final_weight_kg (the weighbridge weight) is required")
        check_weight(body.final_weight_kg)
        await confirm_delivery(db, job, factory, body.final_weight_kg)
    else:
        if not body.reason.strip():
            raise HTTPException(422, "A reason is required to reject a lot")
        await reject_delivery(db, job, factory, body.reason.strip())
    out = await job_out(db, job.id)
    await db.commit()
    await events.publish("ledger.updated", str(job.id))
    await events.publish("job.updated", str(job.id))
    return out


# --- F4 (admin demo button; the Twilio dial-out itself belongs to the voice plan) ---------


@router.post("/{job_id}/verification-call", response_model=VerificationCallOut)
async def post_jobs_job_id_verification_call(
    db: DbSession, events: Events, job_id: str, user: AuthUser = as_admin
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
    await db.commit()
    await events.publish("job.updated", str(job.id))
    return out
