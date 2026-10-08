"""Deciding what one imported row does to its record.

Pure: the caller fetches the stored record and saves what comes back.
Every timestamp is the file's run start (`ImportSighting.started_at`),
never the import's clock, so importing a file twice, or in any order,
leaves the same records (DOMAIN_MODEL DM-6, DM-7).
"""

import dataclasses
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any, TypeVar

from data_reaper.domain.model.entities import DatasetEvent, DatasetPlace
from data_reaper.domain.rules.dataset_rows import NormalizedRow

DatasetRecord = DatasetPlace | DatasetEvent
RecordT = TypeVar("RecordT", DatasetPlace, DatasetEvent)

TRACKING_FIELDS: frozenset[str] = frozenset(
    {
        "id",
        "source",
        "item_id",
        "content_hash",
        "created_at",
        "updated_at",
        "last_seen_at",
        "crawler_id",
        "last_execution_id",
        "last_import_id",
    }
)
"""Fields about where and when a record was seen, never its content."""

UNHASHED_CONTENT_FIELDS: frozenset[str] = frozenset({"source_url"})
"""Content fields left out of `content_hash`: a detail page's
URL changes with tracking parameters, not with the item."""


@dataclass(frozen=True)
class ImportSighting:
    """Who saw a row, and when: the import and its file's run."""

    import_id: str
    crawler_id: str | None
    execution_id: str | None
    started_at: datetime


@dataclass(frozen=True)
class RowOutcome:
    """What one row did: `inserted`, `updated`, `unchanged`, `rejected`.

    `record` is what to save (`None` when rejected); `reason` says why a
    row was rejected. `changed_fields` names, sorted, the content fields
    an `updated` row changed; it is empty for every other outcome.
    """

    outcome: str
    record: DatasetRecord | None = None
    reason: str | None = None
    changed_fields: tuple[str, ...] = ()


def compute_content_hash(record: DatasetRecord) -> str:
    """Return a SHA-256 of the record's normalized content.

    Lists are sorted, so a source reordering categories is no change.
    """
    content = _get_hashed_content(record)
    encoded = json.dumps(content, sort_keys=True, default=str, ensure_ascii=False)
    return hashlib.sha256(encoded.encode()).hexdigest()


def apply_row(
    record_type: type[RecordT],
    stored: RecordT | None,
    row: NormalizedRow,
    sighting: ImportSighting,
    new_id: str,
) -> RowOutcome:
    """Return what upserting `row` onto `stored` gives.

    - No stored record: `inserted`, with `new_id`.
    - A stored record last seen in a newer run than this file's:
      `rejected`, so an older file never overwrites newer data.
    - Otherwise the row's columns are merged onto it: `updated` when
      its content hash changes (`updated_at` moves), `unchanged` when
      not (only `last_seen_at` and the tracking ids move). An update
      names the hashed fields it changed.
    """
    if None is stored:
        return RowOutcome("inserted", _insert(record_type, row, sighting, new_id))
    if stored.last_seen_at > sighting.started_at:
        return RowOutcome(
            "rejected",
            reason=f"{row.item_id}: a newer file already updated this record.",
        )
    merged = dataclasses.replace(stored, **row.content, **_tracking(sighting))
    content_hash = compute_content_hash(merged)
    if content_hash == stored.content_hash:
        return RowOutcome("unchanged", merged)
    updated = dataclasses.replace(
        merged, content_hash=content_hash, updated_at=sighting.started_at
    )
    changed_fields = _get_changed_fields(stored, updated)
    return RowOutcome("updated", updated, changed_fields=changed_fields)


def _insert(
    record_type: type[RecordT],
    row: NormalizedRow,
    sighting: ImportSighting,
    new_id: str,
) -> RecordT:
    """Return a new record for `row`, first seen in this file's run."""
    record = record_type(
        id=new_id,
        source=row.source,
        item_id=row.item_id,
        content_hash="",
        created_at=sighting.started_at,
        updated_at=sighting.started_at,
        **row.content,
        **_tracking(sighting),
    )
    return dataclasses.replace(record, content_hash=compute_content_hash(record))


def _get_hashed_content(record: DatasetRecord) -> dict[str, Any]:
    """Return the fields `content_hash` covers, lists sorted."""
    return {
        name: _normalize(value)
        for name, value in dataclasses.asdict(record).items()
        if name not in TRACKING_FIELDS | UNHASHED_CONTENT_FIELDS
    }


def _get_changed_fields(
    stored: DatasetRecord, updated: DatasetRecord
) -> tuple[str, ...]:
    """Return, sorted, the hashed fields whose values differ."""
    before = _get_hashed_content(stored)
    after = _get_hashed_content(updated)
    return tuple(sorted(name for name in after if before[name] != after[name]))


def _tracking(sighting: ImportSighting) -> dict[str, Any]:
    """Return the tracking fields this sighting sets on a record."""
    return {
        "last_seen_at": sighting.started_at,
        "crawler_id": sighting.crawler_id,
        "last_execution_id": sighting.execution_id,
        "last_import_id": sighting.import_id,
    }


def _normalize(value: Any) -> Any:
    """Return `value` with lists sorted, for a stable hash."""
    if isinstance(value, list):
        return sorted(_normalize(element) for element in value)
    return value
