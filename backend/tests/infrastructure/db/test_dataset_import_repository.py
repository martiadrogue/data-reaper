from datetime import datetime

import pytest
from data_reaper.domain.exceptions import ValidationException
from data_reaper.domain.model.entities import DatasetImport
from data_reaper.domain.model.value_objects import (
    ImportMetrics,
    RowRejection,
)

NOW = datetime(2026, 10, 5, 10)


def _import(import_id: str, file_name: str, **overrides) -> DatasetImport:
    return DatasetImport(
        **{
            "id": import_id,
            "file_name": file_name,
            "created_at": NOW,
            "updated_at": NOW,
            **overrides,
        }
    )


@pytest.mark.anyio
async def test_metrics_and_rejections_round_trip(write_repositories):
    saved = await write_repositories.dataset_imports.save(
        _import(
            "i1",
            "a.csv",
            status="imported",
            metrics=ImportMetrics(3, 1, 1, 0, 1),
            rejections=[RowRejection(2, "rating: bad.")],
            field_changes={"rating": 1},
        )
    )

    fetched = await write_repositories.dataset_imports.get_by_id("i1")

    assert saved == fetched
    assert ImportMetrics(3, 1, 1, 0, 1) == fetched.metrics
    assert [RowRejection(2, "rating: bad.")] == fetched.rejections
    assert {"rating": 1} == fetched.field_changes


@pytest.mark.anyio
async def test_a_file_name_has_one_import(write_repositories):
    await write_repositories.dataset_imports.save(_import("i1", "a.csv"))

    with pytest.raises(ValidationException) as exc_info:
        await write_repositories.dataset_imports.save(_import("i2", "a.csv"))

    assert 409 == exc_info.value.status_code


@pytest.mark.anyio
async def test_listing_filters_by_status_and_counts_each(write_repositories):
    repository = write_repositories.dataset_imports
    await repository.save(_import("i1", "a.csv", status="failed"))
    await repository.save(_import("i2", "b.csv", created_at=datetime(2026, 10, 6)))
    await repository.save(_import("i3", "c.csv"))

    newest_first = await repository.get_all()
    failed = await repository.get_all("failed")

    assert "i2" == newest_first[0].id
    assert ["i1"] == [item.id for item in failed]
    assert {"failed": 1, "pending": 2} == await repository.count_by_status()
    assert {"a.csv", "b.csv", "c.csv"} == await repository.get_all_file_names()


@pytest.mark.anyio
async def test_the_validator_refuses_an_unknown_status(write_repositories):
    with pytest.raises(ValidationException) as exc_info:
        await write_repositories.dataset_imports.save(
            _import("i1", "a.csv", status="done")
        )

    assert 400 == exc_info.value.status_code


@pytest.mark.anyio
async def test_an_import_stored_before_field_changes_reads_none(
    mongo_database, write_repositories
):
    client, database_name = mongo_database
    await client[database_name]["dataset_imports"].insert_one(
        {"_id": "i1", "file_name": "a.csv", "status": "imported"}
        | {"created_at": NOW, "updated_at": NOW}
    )

    fetched = await write_repositories.dataset_imports.get_by_id("i1")

    assert {} == fetched.field_changes


@pytest.mark.anyio
async def test_the_validator_refuses_a_negative_field_change(write_repositories):
    with pytest.raises(ValidationException) as exc_info:
        await write_repositories.dataset_imports.save(
            _import("i1", "a.csv", field_changes={"rating": -1})
        )

    assert 400 == exc_info.value.status_code
