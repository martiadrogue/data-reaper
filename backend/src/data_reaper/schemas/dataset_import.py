"""Response models for Dataset Imports and file discovery."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator

ImportStatus = Literal["pending", "importing", "imported", "failed"]
"""Mirrors `IMPORT_STATUSES` and the `dataset_imports` validator."""


class ImportMetricsOut(BaseModel):
    """What an import did, row by row."""

    model_config = ConfigDict(from_attributes=True)

    rows_read: int
    records_inserted: int
    records_updated: int
    records_unchanged: int
    rows_rejected: int


class RowRejectionOut(BaseModel):
    """One rejected row: its number (header excluded) and why."""

    model_config = ConfigDict(from_attributes=True)

    row_number: int
    reason: str


class FieldChangeOut(BaseModel):
    """How many updated rows of an import changed one content field."""

    field: str
    count: int


class DatasetImportOut(BaseModel):
    """A Dataset Import as returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    file_name: str
    crawler_id: str | None
    execution_id: str | None
    started_at: datetime | None
    dataset: str | None
    status: ImportStatus
    metrics: ImportMetricsOut
    rejections: list[RowRejectionOut]
    field_changes: list[FieldChangeOut]
    error: str | None
    created_at: datetime
    updated_at: datetime
    imported_at: datetime | None

    @field_validator("field_changes", mode="before")
    @classmethod
    def sort_field_changes(cls, value: object) -> object:
        """Return the stored field → count map as a sorted list.

        Most changed first; ties go by field name, so the order is
        stable across requests.
        """
        if not isinstance(value, dict):
            return value
        ranked = sorted(value.items(), key=lambda item: (-item[1], item[0]))
        return [{"field": name, "count": count} for name, count in ranked]


class DatasetImportsPageOut(BaseModel):
    """One page of Dataset Imports, newest first."""

    items: list[DatasetImportOut]
    limit: int
    offset: int
    has_more: bool
    status_counts: dict[str, int]


class DatasetImportQuery(BaseModel):
    """Filters for listing Dataset Imports."""

    status: ImportStatus | None = None


class ImportScanOut(BaseModel):
    """What one scan of the CSV folder found and queued."""

    files_found: int
    imports_created: list[DatasetImportOut]
