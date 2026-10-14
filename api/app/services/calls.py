"""Identity for agent tools: always from the stored call record, never from the model."""
import uuid

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db_models.tables import Call


async def farmer_id_for_call(db: AsyncSession, call_id: str) -> uuid.UUID:
    """Resolve the farmer from the stored call record. Never from anything the model says."""
    try:
        call_uuid = uuid.UUID(call_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Unknown call") from None
    farmer_id = (await db.execute(select(Call.farmer_id).where(Call.id == call_uuid))).first()
    if farmer_id is None:
        raise HTTPException(status_code=404, detail="Unknown call")
    if farmer_id[0] is None:
        raise HTTPException(status_code=409, detail="Call is not linked to a farmer")
    return farmer_id[0]
