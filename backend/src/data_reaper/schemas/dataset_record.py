"""What every dataset record's models share: tracking and filters."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DatasetRecordBase(BaseModel):
    """The key and tracking fields every dataset record has."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    source: str
    item_id: str
    name: str
    source_url: str
    address: str | None
    categories: list[str]
    crawler_id: str | None
    last_execution_id: str | None
    last_import_id: str | None
    created_at: datetime
    updated_at: datetime
    last_seen_at: datetime


class DatasetRecordQuery(BaseModel):
    """Filters for listing a Dataset's records."""

    text: str | None = Field(default=None, min_length=1, max_length=100)
    source: str | None = Field(default=None, min_length=1, max_length=255)
