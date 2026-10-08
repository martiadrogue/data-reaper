"""What one import task needs, opened by `core/di.py`."""

from dataclasses import dataclass

from data_reaper.domain.bundles.repository_factories import (
    RepositorySetFactories,
)
from data_reaper.domain.ports.dataset_file_storage import (
    AbstractDatasetFileStorage,
)
from data_reaper.domain.ports.import_metrics import AbstractImportMetrics


@dataclass(frozen=True)
class ImportInfrastructure:
    """The ports of one Dataset Import run.

    Attributes:
        repository_factories: Opens one short transaction per batch.
        file_storage: Where the validated CSVs are read from.
        import_metrics: Where the finished import is recorded.
        batch_size: Rows written per transaction.
    """

    repository_factories: RepositorySetFactories
    file_storage: AbstractDatasetFileStorage
    import_metrics: AbstractImportMetrics
    batch_size: int
