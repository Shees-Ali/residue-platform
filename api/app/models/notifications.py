"""The bell and a job's timeline. Rules: memory/validation-rules.md, "Events and notifications"."""
from datetime import datetime

from pydantic import BaseModel


class NotificationOut(BaseModel):
    id: str
    type: str
    level: str  # info | warning
    title: str
    body: str
    job_id: str | None = None
    refresh: list[str] = []  # query key roots the screen should refetch
    created_at: datetime
    read: bool


class NotificationPage(BaseModel):
    items: list[NotificationOut]
    next: str | None = None  # pass as ?before= for the next (older) page
    unread: int


class UnreadOut(BaseModel):
    unread: int


class ReadAllOut(BaseModel):
    marked: int


class JobEventOut(BaseModel):
    id: str
    type: str
    summary: str
    actor_role: str | None = None
    created_at: datetime
