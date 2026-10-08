"""Immutable values shared across the domain (no identity)."""

from dataclasses import dataclass


@dataclass(frozen=True)
class GeoLocation:
    """A point on the map, in decimal degrees (WGS 84)."""

    latitude: float
    longitude: float


@dataclass(frozen=True)
class RowRejection:
    """Why one CSV row was not imported.

    `row_number` counts data rows from 1, header excluded, so it is the
    file's line number minus one.
    """

    row_number: int
    reason: str


@dataclass(frozen=True)
class ImportMetrics:
    """Counters of one Dataset Import; every one is ≥ 0.

    `rows_read` = inserted + updated + unchanged + rejected.
    """

    rows_read: int = 0
    records_inserted: int = 0
    records_updated: int = 0
    records_unchanged: int = 0
    rows_rejected: int = 0
