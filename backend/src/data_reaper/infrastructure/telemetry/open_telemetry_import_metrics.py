"""OpenTelemetry implementation of the import metrics port."""

from data_reaper.domain.model.entities import DatasetImport
from data_reaper.domain.ports.import_metrics import AbstractImportMetrics
from opentelemetry.metrics import Meter

# Imports last from under a second to minutes; the SDK's default
# buckets assume milliseconds.
DURATION_BUCKETS_SECONDS = (0.1, 0.5, 1, 2, 5, 10, 30, 60, 120, 300, 600)

_ROW_COUNTERS: tuple[tuple[str, str], ...] = (
    ("records_inserted", "inserted"),
    ("records_updated", "updated"),
    ("records_unchanged", "unchanged"),
    ("rows_rejected", "rejected"),
)


class OpenTelemetryImportMetrics(AbstractImportMetrics):
    """Records finished imports on OpenTelemetry instruments.

    Prometheus sees them as `dataset_imports_total` and
    `dataset_import_duration_seconds` (labelled `dataset`, `status`) and
    `dataset_import_rows_total` (labelled `dataset`, `outcome`). Never
    by import id or file name: one series per file would grow without
    bound.
    """

    def __init__(self, meter: Meter) -> None:
        """Create the instruments on `meter`."""
        self._imports = meter.create_counter(
            "dataset.imports", description="Finished Dataset Imports."
        )
        self._duration = meter.create_histogram(
            "dataset.import.duration",
            unit="s",
            description="From leaving `pending` to `imported` or `failed`.",
            explicit_bucket_boundaries_advisory=DURATION_BUCKETS_SECONDS,
        )
        self._rows = meter.create_counter(
            "dataset.import.rows", description="Imported rows, by outcome."
        )

    def record_finished(
        self, dataset_import: DatasetImport, duration_seconds: float
    ) -> None:
        """Count the import, its duration, and its rows by outcome."""
        dataset = dataset_import.dataset or "unknown"
        with_status = {"dataset": dataset, "status": dataset_import.status}
        self._imports.add(1, with_status)
        self._duration.record(duration_seconds, with_status)
        for metric_name, outcome in _ROW_COUNTERS:
            count = getattr(dataset_import.metrics, metric_name)
            self._rows.add(count, {"dataset": dataset, "outcome": outcome})
