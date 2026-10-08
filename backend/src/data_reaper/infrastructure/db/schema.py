"""Collections, indexes, and `$jsonSchema` validators.

There are no migrations: `initialize_database` runs at startup and is
idempotent. Adding an index or changing a validator here is picked up on
the next start; changing an existing index's options, or reshaping
existing documents, must be done by hand (or `make restart-db`).
"""

import logging
from typing import Any

from data_reaper.domain.model.constants import DATASETS, IMPORT_STATUSES
from pymongo import ASCENDING, DESCENDING, IndexModel
from pymongo.asynchronous.database import AsyncDatabase
from pymongo.errors import CollectionInvalid

logger = logging.getLogger(__name__)

_INTEGER_TYPES = ["int", "long"]
_NUMBER_TYPES = ["double", "int", "long"]


def _enum(*values: str) -> dict[str, Any]:
    """Return a validator rule accepting only `values`."""
    return {"enum": list(values)}


def _integer(minimum: int, is_nullable: bool = False) -> dict[str, Any]:
    """Return a validator rule for an integer of at least `minimum`."""
    bson_types = [*_INTEGER_TYPES, "null"] if is_nullable else _INTEGER_TYPES
    return {"bsonType": bson_types, "minimum": minimum}


def _number(
    minimum: float, maximum: float | None = None, is_nullable: bool = True
) -> dict[str, Any]:
    """Return a validator rule for a number within a range."""
    rule: dict[str, Any] = {
        "bsonType": [*_NUMBER_TYPES, "null"] if is_nullable else _NUMBER_TYPES,
        "minimum": minimum,
    }
    if None is not maximum:
        rule["maximum"] = maximum
    return rule


def _typed(bson_type: str, is_nullable: bool = True) -> dict[str, Any]:
    """Return a validator rule for one BSON type, or `null`."""
    return {"bsonType": [bson_type, "null"] if is_nullable else bson_type}


def _text_list() -> dict[str, Any]:
    """Return a validator rule for a list of strings."""
    return {"bsonType": "array", "items": {"bsonType": "string"}}


def _object(*required: str, **properties: dict[str, Any]) -> dict[str, Any]:
    """Return a `$jsonSchema` validator checking `properties`."""
    schema: dict[str, Any] = {"bsonType": "object", "properties": properties}
    if required:
        schema["required"] = list(required)
    return {"$jsonSchema": schema}


_TRACKING_PROPERTIES: dict[str, dict[str, Any]] = {
    "_id": _typed("string", is_nullable=False),
    "source": _typed("string", is_nullable=False),
    "item_id": _typed("string", is_nullable=False),
    "name": _typed("string", is_nullable=False),
    "source_url": _typed("string", is_nullable=False),
    "content_hash": _typed("string", is_nullable=False),
    "created_at": _typed("date", is_nullable=False),
    "updated_at": _typed("date", is_nullable=False),
    "last_seen_at": _typed("date", is_nullable=False),
    "crawler_id": _typed("string"),
    "last_execution_id": _typed("string"),
    "last_import_id": _typed("string"),
}
"""Every dataset record's key, name, and tracking fields."""

_RECORD_REQUIRED = tuple(_TRACKING_PROPERTIES)

VALIDATORS: dict[str, dict[str, Any]] = {
    "dataset_imports": _object(
        "file_name",
        "status",
        file_name=_typed("string", is_nullable=False),
        status=_enum(*IMPORT_STATUSES),
        dataset={"enum": [*DATASETS, None]},
        started_at=_typed("date"),
        metrics=_object(
            rows_read=_integer(0),
            records_inserted=_integer(0),
            records_updated=_integer(0),
            records_unchanged=_integer(0),
            rows_rejected=_integer(0),
        )["$jsonSchema"],
        field_changes={"bsonType": "object", "additionalProperties": _integer(1)},
    ),
    "dataset_places": _object(
        *_RECORD_REQUIRED,
        **_TRACKING_PROPERTIES,
        address=_typed("string"),
        location={
            "bsonType": ["object", "null"],
            "required": ["latitude", "longitude"],
            "properties": {
                "latitude": _number(-90, 90, is_nullable=False),
                "longitude": _number(-180, 180, is_nullable=False),
            },
        },
        categories=_text_list(),
        rating=_number(0, 10),
        review_count=_integer(0, is_nullable=True),
        price_range=_typed("string"),
        website=_typed("string"),
        phone=_typed("string"),
        opening_hours=_text_list(),
    ),
    "dataset_events": _object(
        *_RECORD_REQUIRED,
        **_TRACKING_PROPERTIES,
        start_date=_typed("date"),
        end_date=_typed("date"),
        timezone=_typed("string"),
        is_all_day=_typed("bool"),
        venue=_typed("string"),
        address=_typed("string"),
        categories=_text_list(),
        organizers=_text_list(),
        cost=_typed("string"),
        price_min=_number(0),
        price_max=_number(0),
        image_url=_typed("string"),
    ),
}
"""Field types, enums, and ranges (DOMAIN_MODEL DM-4, DM-5): each
dataset collection's columns, one property per CSV column."""

_RECORD_INDEXES: list[IndexModel] = [
    IndexModel(
        [("source", ASCENDING), ("item_id", ASCENDING)],
        unique=True,
        name="one_record_per_natural_key",
    ),
    IndexModel([("name", ASCENDING), ("_id", ASCENDING)]),
    IndexModel([("source", ASCENDING), ("name", ASCENDING)]),
    IndexModel("last_import_id"),
]

INDEXES: dict[str, list[IndexModel]] = {
    "dataset_imports": [
        IndexModel("file_name", unique=True),
        IndexModel([("created_at", DESCENDING)]),
        IndexModel([("status", ASCENDING), ("created_at", DESCENDING)]),
    ],
    "dataset_places": _RECORD_INDEXES,
    "dataset_events": [
        *_RECORD_INDEXES,
        IndexModel([("start_date", ASCENDING)]),
    ],
}
"""Natural keys (DM-1, DM-2, DM-3) and listing lookups."""


async def initialize_database(database: AsyncDatabase) -> None:
    """Create missing collections, then apply validators and indexes.

    Collections must exist before the first transaction: MongoDB can't
    create one with a validator inside a transaction.
    """
    existing = set(await database.list_collection_names())
    for name, validator in VALIDATORS.items():
        if name not in existing:
            await _create_collection(database, name, validator)
        else:
            await database.command("collMod", name, validator=validator)
        if INDEXES[name]:
            await database[name].create_indexes(INDEXES[name])
    logger.info("Database initialized: %s", database.name)


async def _create_collection(
    database: AsyncDatabase, name: str, validator: dict[str, Any]
) -> None:
    """Create a collection with its validator.

    Tolerates another process creating it first (several containers
    start at once); the validator is then applied with `collMod`.
    """
    try:
        await database.create_collection(name, validator=validator)
    except CollectionInvalid:
        await database.command("collMod", name, validator=validator)
