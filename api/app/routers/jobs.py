from fastapi import APIRouter, Depends

from app.auth.firebase import current_user
from app.deps import DbSession, Events
from app.routers._stub import todo

router = APIRouter(prefix="/api/jobs", tags=["jobs"], dependencies=[Depends(current_user)])


@router.get("")
async def get_jobs_root(db: DbSession):
    # TODO(A2)
    todo("A2")


@router.get("/{job_id}")
async def get_jobs_job_id(db: DbSession, job_id: str):
    # TODO(A2)
    todo("A2")


@router.post("/{job_id}/pickup")
async def post_jobs_job_id_pickup(db: DbSession, events: Events, job_id: str):
    # TODO(T2)
    todo("T2")


@router.post("/{job_id}/deliver")
async def post_jobs_job_id_deliver(db: DbSession, events: Events, job_id: str):
    # TODO(T2)
    todo("T2")


@router.post("/{job_id}/confirm")
async def post_jobs_job_id_confirm(db: DbSession, events: Events, job_id: str):
    # TODO(FA2)
    todo("FA2")


@router.post("/{job_id}/grade")
async def post_jobs_job_id_grade(db: DbSession, events: Events, job_id: str):
    # TODO(FA2)
    todo("FA2")
