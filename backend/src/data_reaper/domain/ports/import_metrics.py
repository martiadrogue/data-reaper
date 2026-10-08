"""The port for recording finished Dataset Imports for monitoring."""

from abc import ABC, abstractmethod

from data_reaper.domain.model.entities import DatasetImport


class AbstractImportMetrics(ABC):
    """Counts finished imports and their rows, for dashboards."""

    @abstractmethod
    def record_finished(
        self, dataset_import: DatasetImport, duration_seconds: float
    ) -> None:
        """Record an import that ended `imported` or `failed`."""
