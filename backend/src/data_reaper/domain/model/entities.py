"""Framework-agnostic domain entities.

No FastAPI, Pydantic, or PyMongo here, so the domain works the same
behind HTTP, a queue worker, or any storage. See `docs/DOMAIN_MODEL.md`
for the full model.
"""

from dataclasses import dataclass, field
from datetime import datetime

from data_reaper.domain.model.value_objects import (
    GeoLocation,
    ImportMetrics,
    RowRejection,
)


@dataclass
class DatasetImport:
    """One validated CSV file and the state of loading it.

    Created once per file name, so a file is never imported twice by
    discovery; a `failed` one can be retried. `crawler_id`,
    `execution_id`, and `started_at` are read from the file name
    (`<crawler_id>_<execution_id>_<started>.csv`) and are `None` when it
    doesn't follow that pattern, which fails the import. `dataset` is
    detected from the header once the file is read. `field_changes`
    counts, per content field, the updated rows that changed it.
    """

    id: str
    file_name: str
    created_at: datetime
    updated_at: datetime
    crawler_id: str | None = None
    execution_id: str | None = None
    started_at: datetime | None = None
    dataset: str | None = None
    status: str = "pending"
    metrics: ImportMetrics = field(default_factory=ImportMetrics)
    rejections: list[RowRejection] = field(default_factory=list)
    field_changes: dict[str, int] = field(default_factory=dict)
    error: str | None = None
    imported_at: datetime | None = None


@dataclass
class DatasetPlace:
    """A place (restaurant, bar, venue) from a places CSV.

    Keyed by its natural key, `source` + `item_id`. Every column the
    file lacks, or leaves empty, is `None` (`[]` for lists). Tracking
    fields: `content_hash` covers every content field but `source_url`;
    `updated_at` moves only when it changes, `last_seen_at` on every
    import of a newer file that holds the record.
    """

    id: str
    source: str
    item_id: str
    name: str
    source_url: str
    content_hash: str
    created_at: datetime
    updated_at: datetime
    last_seen_at: datetime
    address: str | None = None
    location: GeoLocation | None = None
    categories: list[str] = field(default_factory=list)
    rating: float | None = None
    review_count: int | None = None
    price_range: str | None = None
    website: str | None = None
    phone: str | None = None
    opening_hours: list[str] = field(default_factory=list)
    crawler_id: str | None = None
    last_execution_id: str | None = None
    last_import_id: str | None = None


@dataclass
class DatasetEvent:
    """A scheduled event (a show, a session) from an events CSV.

    Keyed and tracked like `DatasetPlace`. `start_date` and `end_date`
    are wall-clock times in `timezone`, as the source shows them. The
    `all_day` column is stored as `is_all_day`.
    """

    id: str
    source: str
    item_id: str
    name: str
    source_url: str
    content_hash: str
    created_at: datetime
    updated_at: datetime
    last_seen_at: datetime
    start_date: datetime | None = None
    end_date: datetime | None = None
    timezone: str | None = None
    is_all_day: bool | None = None
    venue: str | None = None
    address: str | None = None
    categories: list[str] = field(default_factory=list)
    organizers: list[str] = field(default_factory=list)
    cost: str | None = None
    price_min: float | None = None
    price_max: float | None = None
    image_url: str | None = None
    crawler_id: str | None = None
    last_execution_id: str | None = None
    last_import_id: str | None = None
