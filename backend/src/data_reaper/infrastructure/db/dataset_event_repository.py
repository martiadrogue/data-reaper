"""MongoDB storage for Dataset Events."""

from data_reaper.domain.model.entities import DatasetEvent
from data_reaper.domain.ports.repositories import (
    AbstractDatasetEventRepository,
)
from data_reaper.infrastructure.db.dataset_record_repository import (
    MongoDatasetRecordRepository,
)


class MongoDatasetEventRepository(
    MongoDatasetRecordRepository[DatasetEvent], AbstractDatasetEventRepository
):
    """MongoDB storage for events (`dataset_events`)."""

    entity_type = DatasetEvent
    collection_name = "dataset_events"
