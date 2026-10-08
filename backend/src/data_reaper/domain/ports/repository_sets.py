"""Repository-set ports: every repository, read-only or transactional.

A use case that only reads takes `AbstractReadRepositories`; one that
writes takes `AbstractWriteRepositories` for all of it, reads included.
A read helper shared by both is typed `AbstractRepositories`
(CONTRIBUTING §1.5).
"""

from abc import ABC, abstractmethod
from types import TracebackType
from typing import Self

from data_reaper.domain.ports.repositories import (
    AbstractDatasetEventRepository,
    AbstractDatasetImportRepository,
    AbstractDatasetPlaceRepository,
)


class AbstractRepositories(ABC):
    """Every repository a use case can reach, one per entity."""

    dataset_imports: AbstractDatasetImportRepository
    dataset_places: AbstractDatasetPlaceRepository
    dataset_events: AbstractDatasetEventRepository


class AbstractReadRepositories(AbstractRepositories):
    """Repositories for read-only use cases, outside any transaction.

    There is no snapshot across queries: data may change between two
    reads. Every write method raises `ConfigurationException`, so a
    write can't slip through without a transaction.
    """


class AbstractWriteRepositories(AbstractRepositories):
    """One atomic transaction across every repository (Unit of Work).

    Use it as an async context manager: a clean exit commits, and an
    exception rolls back and propagates.

    async with write_repositories:
        await write_repositories.dataset_imports.save(dataset_import)
        await write_repositories.commit()
    """

    async def __aenter__(self) -> Self:
        """Return these write repositories."""
        return self

    async def __aexit__(
        self,
        exception_type: type[BaseException] | None,
        exception_value: BaseException | None,
        exception_traceback: TracebackType | None,
    ) -> None:
        """Commit on a clean exit; roll back if an exception escaped."""
        if exception_type:
            await self.rollback()
        else:
            await self.commit()

    @abstractmethod
    async def commit(self) -> None:
        """Commit everything staged so far.

        Raises:
            ExternalServiceException: the storage refused the commit
                (503).
        """

    @abstractmethod
    async def rollback(self) -> None:
        """Discard everything staged since the last commit."""
