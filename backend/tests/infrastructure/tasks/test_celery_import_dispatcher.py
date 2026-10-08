from unittest.mock import MagicMock

import pytest
from celery import Celery
from data_reaper.domain.exceptions import ExternalServiceException
from data_reaper.infrastructure.tasks.celery_import_dispatcher import (
    CeleryImportDispatcher,
)
from kombu.exceptions import OperationalError


@pytest.mark.anyio
async def test_sends_the_import_task_by_name_to_the_import_queue():
    app = MagicMock(spec=Celery)

    await CeleryImportDispatcher(app).dispatch("import-1")

    app.send_task.assert_called_once_with(
        "data_reaper.tasks.import_dataset_file",
        args=["import-1"],
        queue="dataset-import",
    )


@pytest.mark.anyio
async def test_an_unreachable_broker_is_an_external_error():
    app = MagicMock(spec=Celery)
    app.send_task.side_effect = OperationalError("connection refused")

    with pytest.raises(ExternalServiceException):
        await CeleryImportDispatcher(app).dispatch("import-1")


def test_the_task_name_matches_the_worker_task():
    from data_reaper.infrastructure.tasks import celery_import_dispatcher
    from data_reaper.presentation.worker import tasks

    assert celery_import_dispatcher.IMPORT_TASK_NAME == tasks.import_dataset_file.name
