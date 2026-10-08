"""Celery tasks: scheduled file discovery, and one import per file.

Each task only opens its infrastructure through `core/di.py` and hands
it, unchanged, to one `services/` function (CONTRIBUTING R1.1.5).
"""

import asyncio

from data_reaper.celery import app
from data_reaper.core.di import (
    create_dataset_file_storage,
    create_import_dispatcher,
    open_import_infrastructure,
    open_task_repositories,
)
from data_reaper.core.logging import bind_import_id
from data_reaper.services import (
    dataset_import_service,
    import_processing_service,
)


async def _discover_dataset_files() -> int:
    """Open the task's repositories and queue the new files."""
    async with open_task_repositories() as repository_factories:
        return await dataset_import_service.dispatch_new_files(
            repository_factories,
            create_dataset_file_storage(),
            create_import_dispatcher(),
        )


async def _import_dataset_file(import_id: str) -> str:
    """Open the import's infrastructure and import one file.

    Every line logged meanwhile carries its `import_id`.
    """
    with bind_import_id(import_id):
        async with open_import_infrastructure() as infrastructure:
            return await import_processing_service.process_import(
                infrastructure, import_id
            )


@app.task(name="data_reaper.tasks.discover_dataset_files")
def discover_dataset_files() -> int:
    """Queue every new validated CSV, from Celery Beat."""
    return asyncio.run(_discover_dataset_files())


@app.task(name="data_reaper.tasks.import_dataset_file")
def import_dataset_file(import_id: str) -> str:
    """Import one validated CSV file."""
    return asyncio.run(_import_dataset_file(import_id))
