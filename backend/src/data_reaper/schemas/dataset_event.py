"""Response models for events (`dataset_events`)."""

from datetime import datetime

from data_reaper.schemas.dataset_record import DatasetRecordBase
from pydantic import BaseModel


class EventOut(DatasetRecordBase):
    """An event as returned by the API (`dataset_events`)."""

    start_date: datetime | None
    end_date: datetime | None
    timezone: str | None
    is_all_day: bool | None
    venue: str | None
    organizers: list[str]
    cost: str | None
    price_min: float | None
    price_max: float | None
    image_url: str | None


class EventsPageOut(BaseModel):
    """One page of events, by name."""

    items: list[EventOut]
    limit: int
    offset: int
    total: int
    has_more: bool
