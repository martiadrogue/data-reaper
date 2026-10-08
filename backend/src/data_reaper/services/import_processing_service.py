"""The use case a worker runs: import one validated CSV file.

1. Claim the import: `pending` → `importing` (anything else is
   skipped, e.g. a redelivered task).
2. Read the file with no transaction open, and detect its Dataset from
   the header.
3. Upsert its rows by natural key, one write transaction per batch.
   A bad row is rejected and recorded; the others go on.
4. Save `imported` with the counters, or `failed` with the reason.

Each batch commits on its own, so a failed import keeps the batches
before the failure; a retry finds them `unchanged`.
"""

import logging
import time
import uuid
from dataclasses import replace
from datetime import UTC, datetime

from data_reaper.domain.bundles.import_batch import (
    ImportBatch,
    ImportTally,
)
from data_reaper.domain.bundles.import_infrastructure import (
    ImportInfrastructure,
)
from data_reaper.domain.bundles.repository_factories import (
    RepositorySetFactories,
)
from data_reaper.domain.exceptions import (
    AppException,
    InvalidRowException,
    ValidationException,
)
from data_reaper.domain.model.constants import (
    DATASET_COLLECTIONS,
    EVENTS_DATASET,
)
from data_reaper.domain.model.entities import (
    DatasetEvent,
    DatasetImport,
    DatasetPlace,
)
from data_reaper.domain.ports.repositories import (
    AbstractDatasetRecordRepository,
)
from data_reaper.domain.ports.repository_sets import (
    AbstractRepositories,
)
from data_reaper.domain.rules.dataset_detection import detect_dataset
from data_reaper.domain.rules.dataset_rows import (
    NormalizedRow,
    normalize_row,
)
from data_reaper.domain.rules.import_file_names import (
    BAD_FILE_NAME_ERROR,
)
from data_reaper.domain.rules.import_tallies import (
    count_changed_fields,
    count_outcome,
)
from data_reaper.domain.rules.record_upserts import (
    DatasetRecord,
    ImportSighting,
    apply_row,
)

logger = logging.getLogger(__name__)

NaturalKey = tuple[str, str]
NumberedRows = list[tuple[int, NormalizedRow]]


async def process_import(infrastructure: ImportInfrastructure, import_id: str) -> str:
    """Import the file of `import_id`; return its final status.

    Returns `skipped` when the import is missing or not `pending`. A
    controlled error (an unreadable file, a header no Dataset fits, a
    database failure) ends it `failed` with that message. Any other
    error ends it `failed` too, then propagates so the worker logs its
    traceback.

    Raises:
        Exception: an unexpected error, after the import is saved
            `failed`.
    """
    clock = time.monotonic()
    factories = infrastructure.repository_factories
    dataset_import = await _start_import(factories, import_id)
    if None is dataset_import:
        return "skipped"
    try:
        finished = await _import_file(infrastructure, dataset_import)
    except AppException as error:
        finished = await _fail_import(factories, dataset_import, error.message)
    except Exception:
        await _fail_import(factories, dataset_import, "Unexpected error; see logs.")
        raise
    infrastructure.import_metrics.record_finished(finished, time.monotonic() - clock)
    logger.info(
        "Import finished: file=%s status=%s metrics=%s",
        finished.file_name,
        finished.status,
        finished.metrics,
    )
    return finished.status


async def _start_import(
    factories: RepositorySetFactories, import_id: str
) -> DatasetImport | None:
    """Move a `pending` import to `importing`; else return `None`."""
    async with factories.open_write() as write_repositories:
        dataset_import = await write_repositories.dataset_imports.get_by_id(import_id)
        if None is dataset_import or "pending" != dataset_import.status:
            logger.info("Import skipped, not pending: id=%s", import_id)
            return None
        return await write_repositories.dataset_imports.save(
            replace(dataset_import, status="importing", updated_at=_now())
        )


async def _import_file(
    infrastructure: ImportInfrastructure, dataset_import: DatasetImport
) -> DatasetImport:
    """Upsert every row of the import's file, batch by batch.

    Raises:
        ValidationException: the file name doesn't parse, the file
            isn't CSV, or no single Dataset fits its header (422).
        ExternalServiceException: the file or database is unreachable.
    """
    if None is dataset_import.started_at:
        raise ValidationException(BAD_FILE_NAME_ERROR, 422)
    dataset_file = await infrastructure.file_storage.read(dataset_import.file_name)
    dataset = detect_dataset(dataset_file.columns)
    sighting = ImportSighting(
        import_id=dataset_import.id,
        crawler_id=dataset_import.crawler_id,
        execution_id=dataset_import.execution_id,
        started_at=dataset_import.started_at,
    )
    tally = ImportTally()
    batch_size = infrastructure.batch_size
    for start in range(0, len(dataset_file.rows), batch_size):
        batch = ImportBatch(
            dataset=dataset,
            rows=dataset_file.rows[start : start + batch_size],
            first_row_number=start + 1,
            sighting=sighting,
        )
        tally = await _import_batch(infrastructure.repository_factories, batch, tally)
    return await _finish_import(
        infrastructure.repository_factories,
        replace(dataset_import, dataset=dataset),
        tally,
    )


async def _import_batch(
    factories: RepositorySetFactories, batch: ImportBatch, tally: ImportTally
) -> ImportTally:
    """Normalize, upsert, and count one batch, in one transaction.

    Rows of the batch that share a natural key merge in file order:
    the second one sees the first as stored.
    """
    normalized, tally = _normalize_rows(batch, tally)
    record_type = _get_record_type(batch.dataset)
    async with factories.open_write() as write_repositories:
        repository = _get_record_repository(write_repositories, batch.dataset)
        stored = await _get_stored_records(repository, normalized)
        touched: dict[NaturalKey, DatasetRecord] = {}
        for row_number, row in normalized:
            key = (row.source, row.item_id)
            outcome = apply_row(
                record_type, stored.get(key), row, batch.sighting, str(uuid.uuid4())
            )
            tally = count_outcome(tally, outcome.outcome, row_number, outcome.reason)
            tally = count_changed_fields(tally, outcome.changed_fields)
            if None is not outcome.record:
                stored[key] = touched[key] = outcome.record
        await repository.save_all(list(touched.values()))
    return tally


def _normalize_rows(
    batch: ImportBatch, tally: ImportTally
) -> tuple[NumberedRows, ImportTally]:
    """Return the batch's valid rows by number, and the new tally.

    A row that can't be normalized is rejected with its reason and the
    batch goes on (CONTRIBUTING R1.6.5: recorded, not swallowed).
    """
    normalized: NumberedRows = []
    for offset, row in enumerate(batch.rows):
        row_number = batch.first_row_number + offset
        try:
            normalized.append((row_number, normalize_row(batch.dataset, row)))
        except InvalidRowException as error:
            tally = count_outcome(tally, "rejected", row_number, error.message)
    return normalized, tally


async def _get_stored_records(
    repository: AbstractDatasetRecordRepository, normalized: NumberedRows
) -> dict[NaturalKey, DatasetRecord]:
    """Return the stored records of the batch's rows, by natural key."""
    item_ids_by_source: dict[str, list[str]] = {}
    for _, row in normalized:
        item_ids_by_source.setdefault(row.source, []).append(row.item_id)
    stored: dict[NaturalKey, DatasetRecord] = {}
    for source, item_ids in item_ids_by_source.items():
        for record in await repository.get_all_by_item_ids(source, item_ids):
            stored[(record.source, record.item_id)] = record
    return stored


async def _finish_import(
    factories: RepositorySetFactories,
    dataset_import: DatasetImport,
    tally: ImportTally,
) -> DatasetImport:
    """Save the import `imported`, with its counters."""
    now = _now()
    async with factories.open_write() as write_repositories:
        return await write_repositories.dataset_imports.save(
            replace(
                dataset_import,
                status="imported",
                metrics=tally.metrics,
                rejections=list(tally.rejections),
                field_changes=dict(tally.field_changes),
                error=None,
                imported_at=now,
                updated_at=now,
            )
        )


async def _fail_import(
    factories: RepositorySetFactories, dataset_import: DatasetImport, error: str
) -> DatasetImport:
    """Save the import `failed` with `error`; earlier batches stay."""
    logger.warning("Import failed: file=%s error=%s", dataset_import.file_name, error)
    async with factories.open_write() as write_repositories:
        return await write_repositories.dataset_imports.save(
            replace(dataset_import, status="failed", error=error, updated_at=_now())
        )


def _get_record_repository(
    repositories: AbstractRepositories, dataset: str
) -> AbstractDatasetRecordRepository:
    """Return the repository of `dataset`'s records."""
    return getattr(repositories, DATASET_COLLECTIONS[dataset])


def _get_record_type(dataset: str) -> type[DatasetPlace] | type[DatasetEvent]:
    """Return the entity `dataset`'s records are."""
    return DatasetEvent if EVENTS_DATASET == dataset else DatasetPlace


def _now() -> datetime:
    """Return the current time, naive UTC like every stored datetime."""
    return datetime.now(UTC).replace(tzinfo=None)
