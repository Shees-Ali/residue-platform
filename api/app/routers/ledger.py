import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select

from app.auth.firebase import AuthUser, as_admin, require_role
from app.auth.owners import transporter_of
from app.db_models.tables import LedgerEntry
from app.deps import DbSession
from app.models.reports import LedgerCheckOut, LedgerEntryOut, PayoutOut
from app.services.reports import farmer_payouts, ledger_check, transporter_payouts

router = APIRouter(prefix="/api/ledger", tags=["ledger"])
as_payee = Depends(require_role("transporter", "farmer"))


@router.get("", response_model=list[LedgerEntryOut])
async def get_ledger_root(
    db: DbSession,
    kind: str | None = None,
    job_id: str | None = None,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    user: AuthUser = as_admin,
):
    """Every ledger entry, newest first (admin)."""
    query = select(LedgerEntry)
    if kind:
        query = query.where(LedgerEntry.kind == kind)
    if job_id:
        try:
            query = query.where(LedgerEntry.job_id == uuid.UUID(job_id))
        except ValueError:
            raise HTTPException(404, "Unknown job") from None
    rows = (
        await db.execute(query.order_by(LedgerEntry.created_at.desc()).limit(limit).offset(offset))
    ).scalars().all()
    return [
        LedgerEntryOut(
            id=str(e.id),
            job_id=str(e.job_id) if e.job_id else None,
            order_id=str(e.order_id) if e.order_id else None,
            kind=e.kind,
            amount=e.amount,
            created_at=e.created_at,
        )
        for e in rows
    ]


@router.get("/check", response_model=LedgerCheckOut)
async def get_ledger_check(db: DbSession, user: AuthUser = as_admin):
    """Escrow in equals releases plus fees plus refunds, for every finished job and order."""
    return await ledger_check(db)


@router.get("/mine", response_model=list[PayoutOut])
async def get_ledger_mine(db: DbSession, user: AuthUser = as_payee):
    """Your payouts. Transporter: pending until the factory confirms, then released.
    Farmer: pending until the job settles, then released."""
    if user.role == "farmer":
        return await farmer_payouts(db, user.uid)
    return await transporter_payouts(db, (await transporter_of(db, user)).id)
