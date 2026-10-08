from datetime import datetime

from data_reaper.domain.model.entities import DatasetImport
from data_reaper.domain.model.value_objects import ImportMetrics
from data_reaper.infrastructure.telemetry.open_telemetry_import_metrics import (
    OpenTelemetryImportMetrics,
)


def _import(**overrides) -> DatasetImport:
    return DatasetImport(
        **{
            "id": "i1",
            "file_name": "a.csv",
            "created_at": datetime(2026, 1, 1),
            "updated_at": datetime(2026, 1, 1),
            "dataset": "places",
            "status": "imported",
            "metrics": ImportMetrics(5, 2, 1, 1, 1),
            **overrides,
        }
    )


def test_counts_the_import_by_dataset_and_status(meter, read_points):
    OpenTelemetryImportMetrics(meter).record_finished(_import(), 1.5)

    [(attributes, point)] = read_points("dataset.imports")
    [(_, duration)] = read_points("dataset.import.duration")
    assert {"dataset": "places", "status": "imported"} == attributes
    assert 1 == point.value
    assert 1.5 == duration.sum


def test_counts_the_rows_by_outcome(meter, read_points):
    OpenTelemetryImportMetrics(meter).record_finished(_import(), 1.0)

    rows = {
        attributes["outcome"]: point.value
        for attributes, point in read_points("dataset.import.rows")
    }
    assert {"inserted": 2, "updated": 1, "unchanged": 1, "rejected": 1} == rows


def test_an_import_without_a_dataset_is_labelled_unknown(meter, read_points):
    OpenTelemetryImportMetrics(meter).record_finished(
        _import(dataset=None, status="failed"), 0.1
    )

    [(attributes, _)] = read_points("dataset.imports")
    assert {"dataset": "unknown", "status": "failed"} == attributes
