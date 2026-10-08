"""The port for enqueuing a Dataset Import on the import queue."""

from abc import ABC, abstractmethod


class AbstractImportDispatcher(ABC):
    """Sends a stored, committed Dataset Import to a worker."""

    @abstractmethod
    async def dispatch(self, import_id: str) -> None:
        """Enqueue the import of `import_id`.

        Raises:
            ExternalServiceException: the queue is unreachable.
        """
