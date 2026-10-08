from dataclasses import replace

import pytest
from csv_samples import PLACES_HEADER, file_name, place_line
from data_reaper.domain.exceptions import (
    ExternalServiceException,
    ValidationException,
)
from data_reaper.schemas.dataset_import import DatasetImportQuery
from data_reaper.services import dataset_import_service


@pytest.mark.anyio
async def test_discovery_creates_and_queues_new_files_oldest_first(
    write_repositories, file_storage, import_dispatcher
):
    newer = file_storage.add(file_name(2, "20261005T120000Z"), PLACES_HEADER)
    older = file_storage.add(file_name(1, "20261001T090000Z"), PLACES_HEADER)

    scan = await dataset_import_service.discover_files(
        write_repositories, file_storage, import_dispatcher
    )

    assert 2 == scan.files_found
    assert [older, newer] == [item.file_name for item in scan.imports_created]
    assert [item.id for item in scan.imports_created] == import_dispatcher.dispatched
    assert {"pending"} == {item.status for item in scan.imports_created}


@pytest.mark.anyio
async def test_discovery_never_queues_a_file_twice(
    write_repositories, file_storage, import_dispatcher
):
    file_storage.add(file_name(1), PLACES_HEADER)
    await dataset_import_service.discover_files(
        write_repositories, file_storage, import_dispatcher
    )

    again = await dataset_import_service.discover_files(
        write_repositories, file_storage, import_dispatcher
    )

    assert [] == again.imports_created
    assert 1 == len(import_dispatcher.dispatched)


@pytest.mark.anyio
async def test_a_badly_named_file_fails_at_once_and_is_not_queued(
    write_repositories, file_storage, import_dispatcher
):
    file_storage.add("export.csv", PLACES_HEADER)

    scan = await dataset_import_service.discover_files(
        write_repositories, file_storage, import_dispatcher
    )

    [created] = scan.imports_created
    assert "failed" == created.status
    assert created.error.startswith("The file name doesn't follow")
    assert [] == import_dispatcher.dispatched


@pytest.mark.anyio
async def test_an_unreachable_folder_fails_discovery(
    write_repositories, file_storage, import_dispatcher
):
    file_storage.is_failing = True

    with pytest.raises(ExternalServiceException):
        await dataset_import_service.discover_files(
            write_repositories, file_storage, import_dispatcher
        )


@pytest.mark.anyio
async def test_dispatch_new_files_opens_its_own_transaction(
    repository_factories, read_repositories, file_storage, import_dispatcher
):
    file_storage.add(file_name(1), PLACES_HEADER, place_line("r1"))

    created = await dataset_import_service.dispatch_new_files(
        repository_factories, file_storage, import_dispatcher
    )

    assert 1 == created
    assert 1 == len(await read_repositories.dataset_imports.get_all())


@pytest.mark.anyio
async def test_imports_list_newest_first_with_counts(
    write_repositories, read_repositories, file_storage, import_dispatcher
):
    file_storage.add(file_name(1), PLACES_HEADER)
    file_storage.add("export.csv", PLACES_HEADER)
    await dataset_import_service.discover_files(
        write_repositories, file_storage, import_dispatcher
    )

    page = await dataset_import_service.get_imports(
        read_repositories, DatasetImportQuery()
    )
    failed = await dataset_import_service.get_imports(
        read_repositories, DatasetImportQuery(status="failed")
    )

    assert 2 == len(page.items)
    assert {"pending": 1, "failed": 1} == page.status_counts
    assert ["export.csv"] == [item.file_name for item in failed.items]


@pytest.mark.anyio
async def test_get_import_of_an_unknown_id_is_404(read_repositories):
    with pytest.raises(ValidationException) as exc_info:
        await dataset_import_service.get_import(read_repositories, "missing")

    assert 404 == exc_info.value.status_code


@pytest.mark.anyio
async def test_retry_puts_a_failed_import_back_in_the_queue(
    write_repositories, file_storage, import_dispatcher
):
    file_storage.add(file_name(1), PLACES_HEADER)
    scan = await dataset_import_service.discover_files(
        write_repositories, file_storage, import_dispatcher
    )
    stored = await write_repositories.dataset_imports.get_by_id(
        scan.imports_created[0].id
    )
    await write_repositories.dataset_imports.save(
        replace(
            stored, status="failed", error="Disk gone.", field_changes={"rating": 3}
        )
    )

    retried = await dataset_import_service.retry_import(
        write_repositories, import_dispatcher, stored.id
    )

    assert ("pending", None) == (retried.status, retried.error)
    assert [] == retried.field_changes
    assert [stored.id, stored.id] == import_dispatcher.dispatched


@pytest.mark.anyio
async def test_an_imported_file_cannot_be_retried(
    write_repositories, file_storage, import_dispatcher
):
    file_storage.add(file_name(1), PLACES_HEADER)
    scan = await dataset_import_service.discover_files(
        write_repositories, file_storage, import_dispatcher
    )
    stored = await write_repositories.dataset_imports.get_by_id(
        scan.imports_created[0].id
    )
    await write_repositories.dataset_imports.save(replace(stored, status="imported"))

    with pytest.raises(ValidationException) as exc_info:
        await dataset_import_service.retry_import(
            write_repositories, import_dispatcher, stored.id
        )

    assert 409 == exc_info.value.status_code
