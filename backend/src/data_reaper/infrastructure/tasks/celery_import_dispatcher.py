"""Celery implementation of the import dispatcher port."""

from celery import Celery
from data_reaper.domain.exceptions import ExternalServiceException
from data_reaper.domain.model.constants import IMPORT_QUEUE
from data_reaper.domain.ports.import_dispatcher import (
    AbstractImportDispatcher,
)
from kombu.exceptions import KombuError

IMPORT_TASK_NAME = "data_reaper.tasks.import_dataset_file"


class CeleryImportDispatcher(AbstractImportDispatcher):
    """Enqueues imports by Celery task name, on `IMPORT_QUEUE`.

    Sending by name avoids importing `presentation/worker/tasks.py`,
    which depends on `services/`; infrastructure may only depend on the
    domain.
    """

    def __init__(self, app: Celery) -> None:
        """Send tasks through the given Celery app."""
        self._app = app

    async def dispatch(self, import_id: str) -> None:
        """Enqueue `import_dataset_file` for `import_id`.

        Raises:
            ExternalServiceException: the broker refused the message.
        """
        try:
            self._app.send_task(IMPORT_TASK_NAME, args=[import_id], queue=IMPORT_QUEUE)
        except (KombuError, OSError) as error:
            raise ExternalServiceException(
                f"Could not enqueue the import: {error}"
            ) from error
