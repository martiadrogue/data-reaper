"""Use cases for finding new CSV files and tracking their imports.

Discovery creates one `pending` Dataset Import per file name it has
never seen, commits, then enqueues each; the worker does the import
(`import_processing_service`).
"""

import logging
import uuid
from dataclasses import replace
from datetime import UTC, datetime

from data_reaper.domain.bundles.repository_factories import (
    RepositorySetFactories,
)
from data_reaper.domain.exceptions import ValidationException
from data_reaper.domain.model.entities import DatasetImport
from data_reaper.domain.model.value_objects import ImportMetrics
from data_reaper.domain.ports.dataset_file_storage import (
    AbstractDatasetFileStorage,
)
from data_reaper.domain.ports.import_dispatcher import (
    AbstractImportDispatcher,
)
from data_reaper.domain.ports.repository_sets import (
    AbstractReadRepositories,
    AbstractRepositories,
    AbstractWriteRepositories,
)
from data_reaper.domain.rules.import_file_names import (
    BAD_FILE_NAME_ERROR,
    parse_import_file_name,
    sort_file_names_oldest_first,
)
from data_reaper.domain.rules.pagination import MAX_PAGE_SIZE, resolve_page
from data_reaper.schemas.dataset_import import (
    DatasetImportOut,
    DatasetImportQuery,
    DatasetImportsPageOut,
    ImportScanOut,
)

logger = logging.getLogger(__name__)


def to_import_out(dataset_import: DatasetImport) -> DatasetImportOut:
    """Map a Dataset Import onto its API schema."""
    return DatasetImportOut.model_validate(dataset_import)


async def discover_files(
    write_repositories: AbstractWriteRepositories,
    file_storage: AbstractDatasetFileStorage,
    import_dispatcher: AbstractImportDispatcher,
) -> ImportScanOut:
    """Create and enqueue an import for every file not seen before.

    Files are queued oldest run first. A file whose name doesn't parse
    gets a `failed` import at once and is never queued, so it shows up
    for a person to look at instead of being retried forever.

    Raises:
        ExternalServiceException: the folder can't be listed, or the
            queue is unreachable (the imports stay `pending`; retry
            them).
        ValidationException: another scan created the same import
            first (409).
    """
    file_names = await file_storage.get_file_names()
    known_names = await write_repositories.dataset_imports.get_all_file_names()
    new_names = sort_file_names_oldest_first(
        [name for name in file_names if name not in known_names]
    )
    created = [
        await write_repositories.dataset_imports.save(_create_import(name))
        for name in new_names
    ]
    await write_repositories.commit()

    await _dispatch_pending(import_dispatcher, created)
    logger.info("Scan: %d CSV files, %d new.", len(file_names), len(created))
    return ImportScanOut(
        files_found=len(file_names),
        imports_created=[to_import_out(item) for item in created],
    )


async def dispatch_new_files(
    repository_factories: RepositorySetFactories,
    file_storage: AbstractDatasetFileStorage,
    import_dispatcher: AbstractImportDispatcher,
) -> int:
    """Run `discover_files` in a transaction of its own (Celery Beat).

    Returns:
        How many imports were created.

    Raises:
        ExternalServiceException: see `discover_files`.
        ValidationException: see `discover_files`.
    """
    async with repository_factories.open_write() as write_repositories:
        scan = await discover_files(write_repositories, file_storage, import_dispatcher)
    return len(scan.imports_created)


async def get_imports(
    read_repositories: AbstractReadRepositories,
    query: DatasetImportQuery,
    limit: int = MAX_PAGE_SIZE,
    offset: int = 0,
) -> DatasetImportsPageOut:
    """Return one page of Dataset Imports, newest first.

    A status filter returns one capped page, like every filtered
    listing (`domain/rules/pagination.py`). Fetches one extra import to
    tell whether more exist.
    """
    page_limit, page_offset = resolve_page(None is not query.status, limit, offset)
    imports = await read_repositories.dataset_imports.get_all(
        query.status, limit=page_limit + 1, offset=page_offset
    )
    return DatasetImportsPageOut(
        items=[to_import_out(item) for item in imports[:page_limit]],
        limit=page_limit,
        offset=page_offset,
        has_more=len(imports) > page_limit,
        status_counts=await read_repositories.dataset_imports.count_by_status(),
    )


async def get_import(
    read_repositories: AbstractReadRepositories, import_id: str
) -> DatasetImportOut:
    """Return one Dataset Import.

    Raises:
        ValidationException: it does not exist (404).
    """
    return to_import_out(await _get_import_or_404(read_repositories, import_id))


async def retry_import(
    write_repositories: AbstractWriteRepositories,
    import_dispatcher: AbstractImportDispatcher,
    import_id: str,
) -> DatasetImportOut:
    """Put an import back to `pending` and enqueue it again.

    Allowed unless it is `imported`: a `failed` one, a `pending` one
    whose message was lost, or an `importing` one whose worker died.
    Importing is idempotent, so a row already written is `unchanged`
    the second time.

    Raises:
        ValidationException: it does not exist (404), or it is already
            imported (409).
        ExternalServiceException: the queue is unreachable.
    """
    dataset_import = await _get_import_or_404(write_repositories, import_id)
    if "imported" == dataset_import.status:
        raise ValidationException("This file is already imported.", 409)

    pending = await write_repositories.dataset_imports.save(
        replace(
            dataset_import,
            status="pending",
            error=None,
            metrics=ImportMetrics(),
            rejections=[],
            field_changes={},
            updated_at=_now(),
        )
    )
    await write_repositories.commit()
    await import_dispatcher.dispatch(pending.id)
    logger.info("Import retried: id=%s", pending.id)
    return to_import_out(pending)


async def _dispatch_pending(
    import_dispatcher: AbstractImportDispatcher, imports: list[DatasetImport]
) -> None:
    """Enqueue the `pending` ones, after their commit."""
    for dataset_import in imports:
        if "pending" == dataset_import.status:
            await import_dispatcher.dispatch(dataset_import.id)


def _create_import(file_name: str) -> DatasetImport:
    """Return a new import for `file_name`: `pending`, or `failed`."""
    now = _now()
    parsed = parse_import_file_name(file_name)
    if None is parsed:
        return DatasetImport(
            id=str(uuid.uuid4()),
            file_name=file_name,
            status="failed",
            error=BAD_FILE_NAME_ERROR,
            created_at=now,
            updated_at=now,
        )
    return DatasetImport(
        id=str(uuid.uuid4()),
        file_name=file_name,
        crawler_id=parsed.crawler_id,
        execution_id=parsed.execution_id,
        started_at=parsed.started_at,
        created_at=now,
        updated_at=now,
    )


async def _get_import_or_404(
    repositories: AbstractRepositories, import_id: str
) -> DatasetImport:
    """Return the Dataset Import.

    Raises:
        ValidationException: it does not exist (404).
    """
    dataset_import = await repositories.dataset_imports.get_by_id(import_id)
    if None is dataset_import:
        raise ValidationException("Dataset import not found.", 404)
    return dataset_import


def _now() -> datetime:
    """Return the current time, naive UTC like every stored datetime."""
    return datetime.now(UTC).replace(tzinfo=None)
