"""F3: a farmer who needs a person, and the admin queue that answers them."""
import uuid

from fastapi import HTTPException
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db_models.tables import Call, Escalation, Farmer
from app.models.escalation import EscalationOut


async def create_escalation(
    db: AsyncSession, call_id: str, summary: str, transcript: str
) -> Escalation:
    row = Escalation(call_id=uuid.UUID(call_id), summary=summary, transcript=transcript)
    db.add(row)
    await db.flush()
    return row


async def list_escalations(
    db: AsyncSession, status: str | None, limit: int, offset: int
) -> list[EscalationOut]:
    query = (
        select(Escalation, Farmer.phone)
        .join(Call, Call.id == Escalation.call_id)
        .outerjoin(Farmer, Farmer.id == Call.farmer_id)
    )
    if status:
        query = query.where(Escalation.status == status)
    rows = (
        await db.execute(query.order_by(Escalation.created_at.desc()).limit(limit).offset(offset))
    ).all()
    return [
        EscalationOut(
            id=str(e.id), call_id=str(e.call_id), summary=e.summary, transcript=e.transcript,
            status=e.status, farmer_phone=phone, created_at=e.created_at,
        )
        for e, phone in rows
    ]


async def resolve_escalation(db: AsyncSession, escalation_id: str, admin_uid: str) -> None:
    try:
        key = uuid.UUID(escalation_id)
    except ValueError:
        raise HTTPException(404, "Unknown escalation") from None
    done = (
        await db.execute(
            update(Escalation)
            .where(Escalation.id == key, Escalation.status == "open")
            .values(status="resolved", resolved_by_uid=admin_uid)
            .returning(Escalation.id)
        )
    ).first()
    if done is None:
        raise HTTPException(409, "Unknown or already resolved escalation")
