"""Counting what each imported row did."""

from dataclasses import replace

from data_reaper.domain.bundles.import_batch import ImportTally
from data_reaper.domain.model.constants import MAX_STORED_REJECTIONS
from data_reaper.domain.model.value_objects import RowRejection

_METRIC_BY_OUTCOME: dict[str, str] = {
    "inserted": "records_inserted",
    "updated": "records_updated",
    "unchanged": "records_unchanged",
    "rejected": "rows_rejected",
}


def count_outcome(
    tally: ImportTally, outcome: str, row_number: int, reason: str | None = None
) -> ImportTally:
    """Return `tally` with one more row of `outcome`.

    A rejected row's reason is kept while fewer than
    `MAX_STORED_REJECTIONS` are; past that the row is only counted.

    Args:
        tally: What the import counted so far.
        outcome: `inserted`, `updated`, `unchanged`, or `rejected`.
        row_number: The row's number, from 1, header excluded.
        reason: Why the row was rejected; ignored otherwise.
    """
    metric_name = _METRIC_BY_OUTCOME[outcome]
    metrics = replace(
        tally.metrics,
        rows_read=tally.metrics.rows_read + 1,
        **{metric_name: getattr(tally.metrics, metric_name) + 1},
    )
    rejections = tally.rejections
    if "rejected" == outcome and len(rejections) < MAX_STORED_REJECTIONS:
        rejections = (*rejections, RowRejection(row_number, reason or "Rejected."))
    return replace(tally, metrics=metrics, rejections=rejections)


def count_changed_fields(
    tally: ImportTally, changed_fields: tuple[str, ...]
) -> ImportTally:
    """Return `tally` with one more change for each of `changed_fields`.

    Args:
        tally: What the import counted so far.
        changed_fields: The content fields one `updated` row changed.
    """
    if not changed_fields:
        return tally
    field_changes = dict(tally.field_changes)
    for field_name in changed_fields:
        field_changes[field_name] = field_changes.get(field_name, 0) + 1
    return replace(tally, field_changes=field_changes)
