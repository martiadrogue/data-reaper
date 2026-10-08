import inspect
from datetime import datetime

import pytest
from data_reaper.core.di import REPOSITORY_FACTORIES
from data_reaper.domain.exceptions import ConfigurationException
from data_reaper.domain.model.entities import DatasetImport
from data_reaper.infrastructure.db.read_repositories import (
    MongoReadRepositories,
)
from data_reaper.infrastructure.db.repository_factories import (
    REPOSITORY_NAMES,
)
from pymongo import AsyncMongoClient

READ_PREFIXES = ("get_", "has_", "count_")


def _public_methods(repository) -> list[str]:
    return [
        name
        for name, _member in inspect.getmembers(
            type(repository), predicate=inspect.isfunction
        )
        if not name.startswith("_")
    ]


@pytest.mark.anyio
async def test_reads_see_committed_data(write_repositories, read_repositories):
    now = datetime(2026, 1, 1)
    await write_repositories.dataset_imports.save(
        DatasetImport(
            id="import-1",
            file_name="c1_e1_20261005T100800Z.csv",
            created_at=now,
            updated_at=now,
        )
    )
    await write_repositories.commit()

    dataset_import = await read_repositories.dataset_imports.get_by_id("import-1")

    assert "c1_e1_20261005T100800Z.csv" == dataset_import.file_name


@pytest.mark.anyio
@pytest.mark.parametrize("repository_name", REPOSITORY_NAMES)
async def test_every_write_method_is_refused(read_repositories, repository_name):
    wrapped = getattr(read_repositories, repository_name)
    write_methods = [
        name
        for name in _public_methods(REPOSITORY_FACTORIES[repository_name])
        if not name.startswith(READ_PREFIXES)
    ]

    assert write_methods
    for name in write_methods:
        with pytest.raises(ConfigurationException):
            getattr(wrapped, name)()


def test_every_repository_port_must_be_bound():
    # Checked in the constructor, before the client is ever used.
    client = AsyncMongoClient(connect=False)
    partial = {
        name: factory
        for name, factory in REPOSITORY_FACTORIES.items()
        if "dataset_places" != name
    }

    with pytest.raises(ConfigurationException) as exc_info:
        MongoReadRepositories(client, "unused", partial)

    assert "dataset_places" in exc_info.value.message
