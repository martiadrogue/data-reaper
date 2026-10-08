import pytest
from data_reaper.domain.exceptions import (
    ExternalServiceException,
    ValidationException,
)
from data_reaper.infrastructure.storage.local_dataset_file_storage import (
    LocalDatasetFileStorage,
)


@pytest.mark.anyio
async def test_lists_only_the_folders_own_csv_files(tmp_path):
    (tmp_path / "b.csv").write_text("item_id\n")
    (tmp_path / "a.CSV").write_text("item_id\n")
    (tmp_path / "notes.txt").write_text("x")
    (tmp_path / "nested").mkdir()
    (tmp_path / "nested" / "c.csv").write_text("item_id\n")

    names = await LocalDatasetFileStorage(str(tmp_path)).get_file_names()

    assert ["a.CSV", "b.csv"] == names


@pytest.mark.anyio
async def test_reads_the_header_and_rows_with_quoted_cells(tmp_path):
    (tmp_path / "a.csv").write_text(
        '﻿item_id,name,categories\n1,"Bar, Grill","[""Tapas""]"\n2,Solo\n',
        encoding="utf-8",
    )

    dataset_file = await LocalDatasetFileStorage(str(tmp_path)).read("a.csv")

    assert ("item_id", "name", "categories") == dataset_file.columns
    assert (
        {"item_id": "1", "name": "Bar, Grill", "categories": '["Tapas"]'},
        {"item_id": "2", "name": "Solo", "categories": ""},
    ) == dataset_file.rows


@pytest.mark.anyio
@pytest.mark.parametrize("name", ["../a.csv", "sub/a.csv", ".."])
async def test_refuses_a_name_with_a_path(tmp_path, name):
    with pytest.raises(ValidationException) as exc_info:
        await LocalDatasetFileStorage(str(tmp_path)).read(name)

    assert 422 == exc_info.value.status_code


@pytest.mark.anyio
async def test_a_file_that_isnt_utf8_csv_is_a_validation_error(tmp_path):
    (tmp_path / "latin.csv").write_bytes("item_id\ncaf\xe9\n".encode("latin-1"))
    (tmp_path / "empty.csv").write_text("")
    storage = LocalDatasetFileStorage(str(tmp_path))

    for name in ("latin.csv", "empty.csv"):
        with pytest.raises(ValidationException):
            await storage.read(name)


@pytest.mark.anyio
async def test_a_missing_file_or_folder_is_an_external_error(tmp_path):
    with pytest.raises(ExternalServiceException):
        await LocalDatasetFileStorage(str(tmp_path)).read("missing.csv")
    with pytest.raises(ExternalServiceException):
        await LocalDatasetFileStorage(str(tmp_path / "missing")).get_file_names()
