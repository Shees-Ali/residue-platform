from datetime import datetime

from pydantic import BaseModel


class TrackPoint(BaseModel):
    kind: str  # pickup | delivery | ping
    lat: float
    lon: float
    at: datetime
    accuracy_m: float | None = None
    distance_from_target_m: int | None = None


class Place(BaseModel):
    lat: float
    lon: float
    name: str | None = None


class TrackOut(BaseModel):
    """Everything the map needs for one job."""

    job_id: str
    state: str
    pickup: Place
    factory: Place
    points: list[TrackPoint]  # oldest first
    last: TrackPoint | None = None
    heading_to: str | None = None  # pickup | factory, while the job is moving
    distance_to_target_km: float | None = None
    eta_minutes: int | None = None  # straight line at an assumed speed, so only "about"
    pickup_off_site_m: int | None = None
    delivery_off_site_m: int | None = None


class ActiveTrack(BaseModel):
    job_id: str
    state: str
    residue_type: str
    quantity_tonnes: float
    village: str | None
    factory_name: str
    pickup: Place
    factory: Place
    last: TrackPoint | None = None
    heading_to: str | None = None
    distance_to_target_km: float | None = None
    eta_minutes: int | None = None
