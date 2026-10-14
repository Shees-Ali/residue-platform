"""Ownership: which factory or transporter row belongs to the signed-in user."""
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.firebase import AuthUser
from app.db_models.tables import Factory, Transporter


async def factory_of(db: AsyncSession, user: AuthUser) -> Factory:
    factory = (
        await db.execute(select(Factory).where(Factory.user_uid == user.uid))
    ).scalar_one_or_none()
    if factory is None:
        raise HTTPException(403, "No factory is linked to this account")
    return factory


async def transporter_of(db: AsyncSession, user: AuthUser) -> Transporter:
    transporter = (
        await db.execute(select(Transporter).where(Transporter.user_uid == user.uid))
    ).scalar_one_or_none()
    if transporter is None:
        raise HTTPException(403, "No transporter is linked to this account")
    return transporter
