"""What the import use case passes between its batches."""

from collections.abc import Sequence
from dataclasses import dataclass, field

from data_reaper.domain.model.value_objects import (
    ImportMetrics,
    RowRejection,
)
from data_reaper.domain.rules.record_upserts import ImportSighting


@dataclass(frozen=True)
class ImportBatch:
    """One batch of a file's rows, written in one transaction.

    Attributes:
        dataset: The Dataset detected from the file's header.
        rows: The batch's rows, as read.
        first_row_number: The first row's number, counting from 1
            without the header.
        sighting: The import and run every row is seen in.
    """

    dataset: str
    rows: Sequence[dict[str, str]]
    first_row_number: int
    sighting: ImportSighting


@dataclass(frozen=True)
class ImportTally:
    """What an import's batches did so far.

    `rejections` holds at most `MAX_STORED_REJECTIONS` reasons; every
    rejected row is still counted in `metrics.rows_rejected`.
    `field_changes` counts, per content field, the `updated` rows that
    changed it; it is replaced, never mutated.
    """

    metrics: ImportMetrics = field(default_factory=ImportMetrics)
    rejections: tuple[RowRejection, ...] = ()
    field_changes: dict[str, int] = field(default_factory=dict)
