"""Response models for Datasets: what each collection holds."""

from pydantic import BaseModel


class DatasetOut(BaseModel):
    """One Dataset: its collection, columns, and records per source."""

    name: str
    collection: str
    columns: list[str]
    record_count: int
    source_counts: dict[str, int]
