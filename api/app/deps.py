"""Shared FastAPI dependencies for routers."""
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.services.events import EventSink, get_events

DbSession = Annotated[AsyncSession, Depends(get_session)]
Events = Annotated[EventSink, Depends(get_events)]
