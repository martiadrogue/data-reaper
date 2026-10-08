import pytest
from data_reaper.core import di
from data_reaper.domain.ports.repository_sets import AbstractRepositories
from data_reaper.infrastructure.storage.local_dataset_file_storage import (
    LocalDatasetFileStorage,
)


def _use_settings(monkeypatch, **values) -> None:
    monkeypatch.setattr(di, "_settings", di._settings.model_copy(update=values))


def test_every_repository_port_has_an_adapter():
    assert set(AbstractRepositories.__annotations__) == set(di.REPOSITORY_FACTORIES)


@pytest.mark.anyio
async def test_the_file_storage_reads_the_configured_folder(monkeypatch, tmp_path):
    (tmp_path / "a.csv").write_text("item_id\n1\n")
    _use_settings(monkeypatch, dataset_import_dir=str(tmp_path))

    storage = di.create_dataset_file_storage()

    assert isinstance(storage, LocalDatasetFileStorage)
    assert ["a.csv"] == await storage.get_file_names()


@pytest.mark.anyio
async def test_import_infrastructure_carries_the_batch_size(monkeypatch):
    _use_settings(monkeypatch, import_batch_size=7)

    async with di.open_import_infrastructure() as infrastructure:
        assert 7 == infrastructure.batch_size


def test_accounts_have_no_local_repository():
    assert "users" not in di.REPOSITORY_FACTORIES
