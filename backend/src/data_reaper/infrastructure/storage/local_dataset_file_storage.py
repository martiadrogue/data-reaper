"""Validated CSVs read from a folder on the local filesystem."""

import asyncio
import csv
import os
from pathlib import Path

from data_reaper.domain.exceptions import (
    ExternalServiceException,
    ValidationException,
)
from data_reaper.domain.ports.dataset_file_storage import (
    AbstractDatasetFileStorage,
    DatasetFile,
)
from data_reaper.domain.rules.import_file_names import is_csv_file_name


class LocalDatasetFileStorage(AbstractDatasetFileStorage):
    """Reads `<base_dir>/<file_name>.csv`; never writes or moves one.

    Only the folder's own files count (no subfolders). Compose mounts it
    read-only, so an import can't damage the crawler's only copy.
    """

    def __init__(self, base_dir: str) -> None:
        """Read CSVs from `base_dir`."""
        self._base_dir = Path(base_dir)

    async def get_file_names(self) -> list[str]:
        """Return every `.csv` file's name, off the event loop.

        Raises:
            ExternalServiceException: the folder is missing or can't be
                listed.
        """
        try:
            return await asyncio.to_thread(_list_csv_names, self._base_dir)
        except OSError as error:
            raise ExternalServiceException(
                f"Could not list the CSV folder {self._base_dir}: {error}"
            ) from error

    async def read(self, file_name: str) -> DatasetFile:
        """Return the file's header and rows, read off the event loop.

        UTF-8, with or without a byte-order mark. A row shorter than
        the header gets `""` for its missing cells; cells beyond the
        header are dropped.

        Raises:
            ValidationException: the name has a path in it, or the file
                isn't UTF-8 CSV with a header (422).
            ExternalServiceException: the file is missing or unreadable.
        """
        if file_name != os.path.basename(file_name) or file_name in ("", ".", ".."):
            raise ValidationException(f"Not a plain file name: {file_name!r}.", 422)
        path = self._base_dir / file_name
        try:
            return await asyncio.to_thread(_read_csv, path)
        except (UnicodeDecodeError, csv.Error) as error:
            raise ValidationException(
                f"{file_name} is not a valid UTF-8 CSV: {error}", 422
            ) from error
        except OSError as error:
            raise ExternalServiceException(f"Could not read {path}: {error}") from error


def _list_csv_names(base_dir: Path) -> list[str]:
    """Return the names of the regular `.csv` files in `base_dir`."""
    return sorted(
        entry.name
        for entry in os.scandir(base_dir)
        if entry.is_file() and is_csv_file_name(entry.name)
    )


def _read_csv(path: Path) -> DatasetFile:
    """Parse `path` as CSV with a header row.

    Raises:
        csv.Error: the file has no header row.
    """
    with path.open(newline="", encoding="utf-8-sig") as csv_file:
        reader = csv.DictReader(csv_file, restval="")
        columns = tuple(reader.fieldnames or ())
        if not columns:
            raise csv.Error("no header row")
        rows = tuple(_fill_row(columns, row) for row in reader)
    return DatasetFile(columns=columns, rows=rows)


def _fill_row(columns: tuple[str, ...], row: dict) -> dict[str, str]:
    """Return the cell of each header column, `""` when missing."""
    return {column: row.get(column) or "" for column in columns}
