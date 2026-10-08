"""Response models for places (`dataset_places`)."""

from data_reaper.schemas.dataset_record import DatasetRecordBase
from pydantic import BaseModel, ConfigDict


class LocationOut(BaseModel):
    """A point on the map, in decimal degrees."""

    model_config = ConfigDict(from_attributes=True)

    latitude: float
    longitude: float


class PlaceOut(DatasetRecordBase):
    """A place as returned by the API (`dataset_places`)."""

    location: LocationOut | None
    rating: float | None
    review_count: int | None
    price_range: str | None
    website: str | None
    phone: str | None
    opening_hours: list[str]


class PlacesPageOut(BaseModel):
    """One page of places, by name."""

    items: list[PlaceOut]
    limit: int
    offset: int
    total: int
    has_more: bool
