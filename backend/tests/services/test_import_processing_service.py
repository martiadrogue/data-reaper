from dataclasses import replace

import pytest
from csv_samples import (
    EVENTS_HEADER,
    PLACES_HEADER,
    event_line,
    file_name,
    place_line,
)
from data_reaper.domain.bundles.import_infrastructure import (
    ImportInfrastructure,
)
from data_reaper.domain.bundles.record_query import RecordQuery
from data_reaper.domain.model.constants import MAX_STORED_REJECTIONS
from data_reaper.services import (
    dataset_import_service,
    import_processing_service,
)


@pytest.fixture
def infrastructure(repository_factories, file_storage, import_metrics):
    return ImportInfrastructure(
        repository_factories=repository_factories,
        file_storage=file_storage,
        import_metrics=import_metrics,
        batch_size=2,
    )


async def _discover(repository_factories, file_storage, import_dispatcher):
    async with repository_factories.open_write() as write_repositories:
        scan = await dataset_import_service.discover_files(
            write_repositories, file_storage, import_dispatcher
        )
    return [item.id for item in scan.imports_created]


async def _import_all(infrastructure, import_dispatcher):
    factories = infrastructure.repository_factories
    ids = await _discover(factories, infrastructure.file_storage, import_dispatcher)
    return [
        await import_processing_service.process_import(infrastructure, import_id)
        for import_id in ids
    ]


async def _get_import(read_repositories, name):
    imports = await read_repositories.dataset_imports.get_all()
    return next(item for item in imports if name == item.file_name)


@pytest.mark.anyio
async def test_a_places_file_is_upserted_in_batches(
    infrastructure, import_dispatcher, read_repositories, import_metrics
):
    name = infrastructure.file_storage.add(
        file_name(1),
        PLACES_HEADER,
        place_line("r1"),
        place_line("r2"),
        place_line("r3"),
    )

    assert ["imported"] == await _import_all(infrastructure, import_dispatcher)

    dataset_import = await _get_import(read_repositories, name)
    places = await read_repositories.dataset_places.get_all(RecordQuery())
    assert "places" == dataset_import.dataset
    assert (3, 3, 0) == (
        dataset_import.metrics.rows_read,
        dataset_import.metrics.records_inserted,
        dataset_import.metrics.rows_rejected,
    )
    assert {"r1", "r2", "r3"} == {place.item_id for place in places}
    assert {"thefork.es"} == {place.source for place in places}
    assert {dataset_import.id} == {place.last_import_id for place in places}
    assert [dataset_import.id] == [item.id for item in import_metrics.finished]


@pytest.mark.anyio
async def test_a_newer_file_updates_changed_records_only(
    infrastructure, import_dispatcher, read_repositories
):
    storage = infrastructure.file_storage
    storage.add(
        file_name(1, "20261001T090000Z"),
        PLACES_HEADER,
        place_line("r1"),
        place_line("r2"),
    )
    newer = storage.add(
        file_name(2, "20261005T090000Z"),
        PLACES_HEADER,
        place_line("r1"),
        place_line("r2", rating="7.5"),
        place_line("r3"),
    )

    await _import_all(infrastructure, import_dispatcher)

    metrics = (await _get_import(read_repositories, newer)).metrics
    assert (1, 1, 1) == (
        metrics.records_inserted,
        metrics.records_updated,
        metrics.records_unchanged,
    )
    assert 3 == await read_repositories.dataset_places.count_all(RecordQuery())


@pytest.mark.anyio
async def test_field_changes_add_up_across_batches(
    infrastructure, import_dispatcher, read_repositories
):
    storage = infrastructure.file_storage
    storage.add(
        file_name(1, "20261001T090000Z"),
        PLACES_HEADER,
        place_line("r1"),
        place_line("r2"),
        place_line("r3"),
    )
    newer = storage.add(
        file_name(2, "20261005T090000Z"),
        PLACES_HEADER,
        place_line("r1", rating="7.5"),
        place_line("r2"),
        place_line("r3", name="Arrabal Nou", rating="8"),
        place_line("r4"),
    )

    await _import_all(infrastructure, import_dispatcher)

    dataset_import = await _get_import(read_repositories, newer)
    assert 2 == dataset_import.metrics.records_updated
    assert {"rating": 2, "name": 1} == dataset_import.field_changes


@pytest.mark.anyio
async def test_re_importing_a_file_changes_nothing(
    infrastructure, import_dispatcher, read_repositories, repository_factories
):
    name = infrastructure.file_storage.add(
        file_name(1), PLACES_HEADER, place_line("r1")
    )
    await _import_all(infrastructure, import_dispatcher)
    before = await read_repositories.dataset_places.get_all(RecordQuery())
    dataset_import = await _get_import(read_repositories, name)
    async with repository_factories.open_write() as write_repositories:
        await write_repositories.dataset_imports.save(
            replace(dataset_import, status="pending")
        )

    await import_processing_service.process_import(infrastructure, dataset_import.id)

    after = await read_repositories.dataset_places.get_all(RecordQuery())
    metrics = (await _get_import(read_repositories, name)).metrics
    assert 1 == metrics.records_unchanged
    assert [place.updated_at for place in before] == [
        place.updated_at for place in after
    ]


@pytest.mark.anyio
async def test_bad_rows_are_rejected_and_the_rest_imported(
    infrastructure, import_dispatcher, read_repositories
):
    name = infrastructure.file_storage.add(
        file_name(1),
        PLACES_HEADER,
        place_line("r1"),
        place_line("r2", rating="high"),
        place_line("", name="No id"),
    )

    assert ["imported"] == await _import_all(infrastructure, import_dispatcher)

    dataset_import = await _get_import(read_repositories, name)
    assert (1, 2) == (
        dataset_import.metrics.records_inserted,
        dataset_import.metrics.rows_rejected,
    )
    assert [2, 3] == [rejection.row_number for rejection in dataset_import.rejections]
    assert "rating: expected a number" in dataset_import.rejections[0].reason


@pytest.mark.anyio
async def test_only_the_first_rejections_keep_their_reason(
    infrastructure, import_dispatcher, read_repositories
):
    bad_rows = [place_line(f"r{n}", rating="x") for n in range(25)]
    name = infrastructure.file_storage.add(file_name(1), PLACES_HEADER, *bad_rows)

    await _import_all(infrastructure, import_dispatcher)

    dataset_import = await _get_import(read_repositories, name)
    assert 25 == dataset_import.metrics.rows_rejected
    assert MAX_STORED_REJECTIONS == len(dataset_import.rejections)


@pytest.mark.anyio
async def test_an_events_file_lands_in_events(
    infrastructure, import_dispatcher, read_repositories
):
    infrastructure.file_storage.add(
        file_name(1), EVENTS_HEADER, event_line("29064"), event_line("29079")
    )

    await _import_all(infrastructure, import_dispatcher)

    events = await read_repositories.dataset_events.get_all(RecordQuery())
    assert ["29064", "29079"] == sorted(event.item_id for event in events)
    assert {"thecomedyclubhouse.es"} == {event.source for event in events}
    assert 0 == await read_repositories.dataset_places.count_all(RecordQuery())


@pytest.mark.anyio
async def test_a_header_no_dataset_fits_fails_the_import(
    infrastructure, import_dispatcher, read_repositories, import_metrics
):
    name = infrastructure.file_storage.add(
        file_name(1), "item_id,name,source_url,menu", "1,a,https://x.es/1,b"
    )

    assert ["failed"] == await _import_all(infrastructure, import_dispatcher)

    dataset_import = await _get_import(read_repositories, name)
    assert "Unknown columns: menu." == dataset_import.error
    assert ["failed"] == [item.status for item in import_metrics.finished]


@pytest.mark.anyio
async def test_an_unreadable_file_fails_the_import(
    infrastructure, import_dispatcher, read_repositories
):
    name = infrastructure.file_storage.add(file_name(1), PLACES_HEADER)
    ids = await _discover(
        infrastructure.repository_factories,
        infrastructure.file_storage,
        import_dispatcher,
    )
    infrastructure.file_storage.files.pop(name)

    status = await import_processing_service.process_import(infrastructure, ids[0])

    assert "failed" == status
    assert "No such file" in (await _get_import(read_repositories, name)).error


@pytest.mark.anyio
async def test_an_import_not_pending_is_skipped(infrastructure, import_dispatcher):
    infrastructure.file_storage.add(file_name(1), PLACES_HEADER, place_line("r1"))
    [import_id] = await _discover(
        infrastructure.repository_factories,
        infrastructure.file_storage,
        import_dispatcher,
    )
    await import_processing_service.process_import(infrastructure, import_id)

    assert "skipped" == await import_processing_service.process_import(
        infrastructure, import_id
    )
    assert "skipped" == await import_processing_service.process_import(
        infrastructure, "missing"
    )


@pytest.mark.anyio
async def test_an_unexpected_error_fails_the_import_then_propagates(
    infrastructure, import_dispatcher, read_repositories, monkeypatch
):
    name = infrastructure.file_storage.add(
        file_name(1), PLACES_HEADER, place_line("r1")
    )
    [import_id] = await _discover(
        infrastructure.repository_factories,
        infrastructure.file_storage,
        import_dispatcher,
    )

    def explode(*args):
        raise RuntimeError("boom")

    monkeypatch.setattr(import_processing_service, "apply_row", explode)

    with pytest.raises(RuntimeError):
        await import_processing_service.process_import(infrastructure, import_id)

    dataset_import = await _get_import(read_repositories, name)
    assert ("failed", "Unexpected error; see logs.") == (
        dataset_import.status,
        dataset_import.error,
    )
