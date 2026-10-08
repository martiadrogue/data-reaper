"""The port for the folder of validated CSV files to import."""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class DatasetFile:
    """One CSV file as read: its header and its rows.

    Each row maps every header column to its cell's text, `""` when
    empty or missing.
    """

    columns: tuple[str, ...]
    rows: tuple[dict[str, str], ...]


class AbstractDatasetFileStorage(ABC):
    """Lists and reads the validated CSVs; never changes them."""

    @abstractmethod
    async def get_file_names(self) -> list[str]:
        """Return the name of every CSV file in the folder.

        Raises:
            ExternalServiceException: the folder can't be listed.
        """

    @abstractmethod
    async def read(self, file_name: str) -> DatasetFile:
        """Return the file's header and rows.

        Raises:
            ValidationException: the name isn't a plain file name, or
                the file isn't UTF-8 CSV with a header (422).
            ExternalServiceException: the file is missing or can't be
                read.
        """
