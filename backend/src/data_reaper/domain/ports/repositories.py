"""Repository ports: one abstract storage interface per entity.

Every implementation converts storage errors before they leave it: a
broken natural key or unique reference raises `ValidationException`
(409), a document the storage validator rejects raises
`ValidationException` (400), and any other storage failure raises
`ExternalServiceException` (503).
"""

from abc import ABC, abstractmethod
from typing import Generic, TypeVar

from data_reaper.domain.bundles.record_query import RecordQuery
from data_reaper.domain.model.entities import (
    DatasetEvent,
    DatasetImport,
    DatasetPlace,
)

RecordT = TypeVar("RecordT", DatasetPlace, DatasetEvent)


class AbstractDatasetImportRepository(ABC):
    """Storage for Dataset Imports, one per file name."""

    @abstractmethod
    async def get_by_id(self, import_id: str) -> DatasetImport | None:
        """Return the Dataset Import with this id, if any."""

    @abstractmethod
    async def get_all_file_names(self) -> set[str]:
        """Return the file name of every Dataset Import."""

    @abstractmethod
    async def get_all(
        self,
        status: str | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[DatasetImport]:
        """Return Dataset Imports, newest first.

        Args:
            status: Only those in this status; `None` for every one.
            limit: Maximum to return; `None` returns them all.
            offset: How many to skip first.
        """

    @abstractmethod
    async def count_by_status(self) -> dict[str, int]:
        """Return how many Dataset Imports are in each status."""

    @abstractmethod
    async def save(self, dataset_import: DatasetImport) -> DatasetImport:
        """Insert or update a Dataset Import; return a fresh copy.

        Raises:
            ValidationException: another one already has its file name
                (409).
        """


class AbstractDatasetRecordRepository(ABC, Generic[RecordT]):
    """Storage for one Dataset's records, keyed by source + item id."""

    @abstractmethod
    async def get_by_id(self, record_id: str) -> RecordT | None:
        """Return the record with this id, if any."""

    @abstractmethod
    async def get_all_by_item_ids(
        self, source: str, item_ids: list[str]
    ) -> list[RecordT]:
        """Return the records of `source` with these `item_id`s.

        Ids with no record are left out; the order is unspecified.
        """

    @abstractmethod
    async def get_all(
        self, query: RecordQuery, limit: int | None = None, offset: int = 0
    ) -> list[RecordT]:
        """Return the records matching `query`, by name then id.

        Args:
            query: The filters; an empty one matches every record.
            limit: Maximum to return; `None` returns them all.
            offset: How many to skip first.
        """

    @abstractmethod
    async def count_all(self, query: RecordQuery) -> int:
        """Return how many records match `query`."""

    @abstractmethod
    async def count_by_source(self) -> dict[str, int]:
        """Return how many records each source has."""

    @abstractmethod
    async def save_all(self, records: list[RecordT]) -> list[RecordT]:
        """Insert or replace each record by its id; return copies.

        Raises:
            ValidationException: two records would share a natural key
                (409), or the storage validator rejects one (400).
        """


class AbstractDatasetPlaceRepository(AbstractDatasetRecordRepository[DatasetPlace]):
    """Storage for Dataset Places (`dataset_places`)."""


class AbstractDatasetEventRepository(AbstractDatasetRecordRepository[DatasetEvent]):
    """Storage for Dataset Events (`dataset_events`)."""
