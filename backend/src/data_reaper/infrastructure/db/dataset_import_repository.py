"""MongoDB storage for Dataset Imports."""

from dataclasses import replace
from typing import Any

from data_reaper.domain.model.entities import DatasetImport
from data_reaper.domain.model.value_objects import (
    ImportMetrics,
    RowRejection,
)
from data_reaper.domain.ports.repositories import (
    AbstractDatasetImportRepository,
)
from data_reaper.infrastructure.db.mongo_repository import (
    NEWEST_FIRST,
    MongoRepository,
    translate_errors,
)


class MongoDatasetImportRepository(
    MongoRepository[DatasetImport], AbstractDatasetImportRepository
):
    """MongoDB storage for Dataset Imports; `file_name` is unique.

    `metrics` and `rejections` are embedded documents, rebuilt into
    their value objects on read.
    """

    entity_type = DatasetImport
    collection_name = "dataset_imports"
    conflict_message = "This file already has an import."

    def _to_domain(self, document: dict[str, Any]) -> DatasetImport:
        """Map a document onto an import and its value objects."""
        return replace(
            super()._to_domain(document),
            metrics=ImportMetrics(**document.get("metrics") or {}),
            rejections=[
                RowRejection(**rejection)
                for rejection in document.get("rejections", [])
            ],
        )

    async def get_by_id(self, import_id: str) -> DatasetImport | None:
        """Return the Dataset Import with this id, if any."""
        return await self._find_one({"_id": import_id})

    async def get_all_file_names(self) -> set[str]:
        """Return the file name of every Dataset Import."""
        with translate_errors(self.conflict_message):
            file_names = await self._collection.distinct(
                "file_name", session=self._session
            )
        return set(file_names)

    async def get_all(
        self,
        status: str | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[DatasetImport]:
        """Return Dataset Imports, newest first."""
        query = {} if None is status else {"status": status}
        return await self._find_many(query, NEWEST_FIRST, limit, offset)

    async def count_by_status(self) -> dict[str, int]:
        """Return how many Dataset Imports are in each status."""
        pipeline = [{"$group": {"_id": "$status", "count": {"$sum": 1}}}]
        with translate_errors(self.conflict_message):
            cursor = await self._collection.aggregate(pipeline, session=self._session)
            db_groups = await cursor.to_list()
        return {db_group["_id"]: db_group["count"] for db_group in db_groups}

    async def save(self, dataset_import: DatasetImport) -> DatasetImport:
        """Insert or update a Dataset Import; return a fresh copy.

        Raises:
            ValidationException: another one already has its file name
                (409).
        """
        return await self._save(dataset_import)
