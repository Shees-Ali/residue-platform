"""Shared FastAPI dependencies for routers."""
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.services.inbox import Inbox, get_inbox

DbSession = Annotated[AsyncSession, Depends(get_session)]
Delivery = Annotated[Inbox, Depends(get_inbox)]
