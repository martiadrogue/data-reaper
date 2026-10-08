"""MongoDB storage for Dataset Places."""

from dataclasses import replace
from typing import Any

from data_reaper.domain.model.entities import DatasetPlace
from data_reaper.domain.model.value_objects import GeoLocation
from data_reaper.domain.ports.repositories import (
    AbstractDatasetPlaceRepository,
)
from data_reaper.infrastructure.db.dataset_record_repository import (
    MongoDatasetRecordRepository,
)


class MongoDatasetPlaceRepository(
    MongoDatasetRecordRepository[DatasetPlace], AbstractDatasetPlaceRepository
):
    """MongoDB storage for places (`dataset_places`).

    `location` is an embedded `{latitude, longitude}` document, rebuilt
    into a `GeoLocation` on read.
    """

    entity_type = DatasetPlace
    collection_name = "dataset_places"

    def _to_domain(self, document: dict[str, Any]) -> DatasetPlace:
        """Map a document onto a place and its location."""
        db_location = document.get("location")
        location = None if None is db_location else GeoLocation(**db_location)
        return replace(super()._to_domain(document), location=location)
