"""Pure helpers between form input, API payloads, and display text.

No Reflex and no I/O here, so every function is unit-tested on its own
(frontend/docs/CONTRIBUTING.md FR1.4).
"""

ALL = "all"
"""The select value that turns a filter off (Radix selects can't hold "")."""

IMPORT_STATUSES = ["pending", "importing", "imported", "failed"]
IMPORT_STATUS_FILTERS = [ALL, *IMPORT_STATUSES]
PAGE_SIZE = 50


def blank_to_none(value: str | None) -> str | None:
    """Return the trimmed text, or `None` when it is blank."""
    text = (value or "").strip()
    return text or None


def import_params(status: str, offset: int) -> dict:
    """Return the query for one page of imports."""
    return {
        "status": None if ALL == status else status,
        "limit": PAGE_SIZE,
        "offset": offset,
    }


def record_params(text: str, source: str, offset: int) -> dict:
    """Return the query for one page of places or events.

    A filtered listing is one page from the top (the API ignores the
    offset), so the offset is only sent unfiltered.
    """
    text_filter = blank_to_none(text)
    source_filter = None if ALL == source else blank_to_none(source)
    is_filtered = text_filter is not None or source_filter is not None
    return {
        "text": text_filter,
        "source": source_filter,
        "limit": PAGE_SIZE,
        "offset": 0 if is_filtered else offset,
    }


def next_offset(page: dict) -> int | None:
    """Return the next page's offset, or `None` on the last page."""
    if not page.get("has_more"):
        return None
    return page["offset"] + page["limit"]


def previous_offset(page: dict) -> int | None:
    """Return the previous page's offset, or `None` on the first."""
    if 0 == page.get("offset", 0):
        return None
    return max(page["offset"] - page["limit"], 0)


def source_options(datasets: list[dict], dataset_name: str) -> list[str]:
    """Return the source filter's options for one Dataset, by name."""
    for dataset in datasets:
        if dataset_name == dataset["name"]:
            return [ALL, *sorted(dataset["source_counts"])]
    return [ALL]


def metrics_summary(metrics: dict) -> str:
    """Return an import's counters as one short line."""
    return (
        f"{metrics.get('records_inserted', 0)} new · "
        f"{metrics.get('records_updated', 0)} updated · "
        f"{metrics.get('records_unchanged', 0)} unchanged · "
        f"{metrics.get('rows_rejected', 0)} rejected"
    )


TOP_FIELD_CHANGES = 3
"""How many changed fields the Imports table shows per import."""


def field_changes_summary(field_changes: list[dict], limit: int | None = None) -> str:
    """Return an import's changed fields and counts as one line.

    The API sends them most changed first; `limit` keeps the first ones.
    """
    return " · ".join(
        f"{change['field']} {change['count']}" for change in field_changes[:limit]
    )


def join_texts(values: list[str] | None) -> str:
    """Return a list of texts as one comma-separated line, `—` if empty."""
    return ", ".join(values or []) or "—"


def with_display_fields(dataset_import: dict) -> dict:
    """Return the import with the texts the Imports table shows."""
    return {
        **dataset_import,
        "metrics_text": metrics_summary(dataset_import.get("metrics") or {}),
        "field_changes_text": field_changes_summary(
            dataset_import.get("field_changes") or [], TOP_FIELD_CHANGES
        ),
        "dataset_text": dataset_import.get("dataset") or "—",
        "is_retryable": "imported" != dataset_import.get("status"),
    }


_DETAIL_FIELDS = (
    "dataset",
    "crawler_id",
    "execution_id",
    "started_at",
    "imported_at",
)


def import_detail(dataset_import: dict) -> dict[str, str]:
    """Return the import's detail as display text, `—` when missing."""
    metrics = dataset_import.get("metrics") or {}
    return {
        **{name: dataset_import.get(name) or "—" for name in _DETAIL_FIELDS},
        "file_name": dataset_import.get("file_name", ""),
        "status": dataset_import.get("status", ""),
        "rows_read": str(metrics.get("rows_read", 0)),
        "metrics": metrics_summary(metrics),
        "field_changes": _all_field_changes_text(dataset_import),
        "error": dataset_import.get("error") or "",
    }


def _all_field_changes_text(dataset_import: dict) -> str:
    """Return every changed field of the import, `—` if none."""
    return field_changes_summary(dataset_import.get("field_changes") or []) or "—"


def with_list_texts(record: dict, *names: str) -> dict:
    """Return the record with a `<name>_text` line for each list field."""
    return {
        **record,
        **{f"{name}_text": join_texts(record.get(name)) for name in names},
    }
