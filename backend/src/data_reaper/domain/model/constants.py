"""Fixed vocabulary of the domain: datasets, columns, statuses, queues.

See `docs/DOMAIN_MODEL.md` §5.2 for what each one means.
"""

PLACES_DATASET = "places"
EVENTS_DATASET = "events"
DATASETS: tuple[str, ...] = (PLACES_DATASET, EVENTS_DATASET)
"""Every Dataset a validated CSV can be imported into."""

PLACE_COLUMNS: tuple[str, ...] = (
    "item_id",
    "name",
    "address",
    "location",
    "categories",
    "rating",
    "review_count",
    "price_range",
    "website",
    "phone",
    "source_url",
    "opening_hours",
)
"""The columns a places CSV may hold; each file has a subset."""

EVENT_COLUMNS: tuple[str, ...] = (
    "item_id",
    "name",
    "start_date",
    "end_date",
    "timezone",
    "all_day",
    "venue",
    "address",
    "categories",
    "organizers",
    "cost",
    "price_min",
    "price_max",
    "image_url",
    "source_url",
)
"""The columns an events CSV may hold; each file has a subset."""

DATASET_COLLECTIONS: dict[str, str] = {
    PLACES_DATASET: "dataset_places",
    EVENTS_DATASET: "dataset_events",
}
"""Each Dataset's collection, also its repository's attribute name."""

DATASET_COLUMNS: dict[str, tuple[str, ...]] = {
    PLACES_DATASET: PLACE_COLUMNS,
    EVENTS_DATASET: EVENT_COLUMNS,
}

REQUIRED_COLUMNS: tuple[str, ...] = ("item_id", "name", "source_url")
"""Columns every file has and every row fills: the natural key and
what identifies the record to a reader."""

IMPORT_STATUSES: tuple[str, ...] = ("pending", "importing", "imported", "failed")
"""A Dataset Import's `status`; `pending` is the default."""

IMPORT_OUTCOMES: tuple[str, ...] = ("inserted", "updated", "unchanged", "rejected")
"""What importing one row did (`RowOutcome.outcome`)."""

IMPORT_QUEUE = "dataset-import"
"""The Celery queue imports and file discovery run on."""

MAX_STORED_REJECTIONS = 20
"""Rejected rows whose reason a Dataset Import keeps; the rest are only
counted, so a broken file never outgrows MongoDB's document limit."""
