"""Reading a validated CSV's file name: who wrote it, and when.

Night Crawler names each execution's CSV
`<crawler_id>_<execution_id>_<started>.csv`, with `<started>` the
run's start in UTC (`20261001T114123Z`).
"""

import re
from dataclasses import dataclass
from datetime import datetime

CSV_SUFFIX = ".csv"

BAD_FILE_NAME_ERROR = (
    "The file name doesn't follow <crawler_id>_<execution_id>_<started>.csv, "
    "so the run that wrote it and when it started are unknown."
)
"""Why an import of a file whose name doesn't parse fails."""

_FILE_NAME_PATTERN = re.compile(
    r"^(?P<crawler_id>[0-9a-f-]{36})_(?P<execution_id>[0-9a-f-]{36})"
    r"_(?P<started>\d{8}T\d{6}Z)\.csv$"
)


@dataclass(frozen=True)
class ImportFileName:
    """What a file name says about the CSV it names.

    `started_at` is naive UTC, like every stored datetime.
    """

    crawler_id: str
    execution_id: str
    started_at: datetime


def is_csv_file_name(file_name: str) -> bool:
    """Return whether `file_name` names a CSV file (any case)."""
    return file_name.lower().endswith(CSV_SUFFIX)


def parse_import_file_name(file_name: str) -> ImportFileName | None:
    """Return what `file_name` encodes, or `None` if it doesn't match.

    A name with the right shape but an impossible timestamp (e.g.
    month 13) doesn't match either.
    """
    match = _FILE_NAME_PATTERN.match(file_name)
    if None is match:
        return None
    try:
        started_at = datetime.strptime(match["started"], "%Y%m%dT%H%M%S%z")
        started_at = started_at.replace(tzinfo=None)
    except ValueError:
        return None
    return ImportFileName(
        crawler_id=match["crawler_id"],
        execution_id=match["execution_id"],
        started_at=started_at,
    )


def sort_file_names_oldest_first(file_names: list[str]) -> list[str]:
    """Return `file_names` by run start, oldest first.

    Importing older runs first means a newer file is never rejected as
    stale only because it was queued first. Names that don't parse go
    last, alphabetically.
    """

    def sort_key(file_name: str) -> tuple[bool, str, str]:
        parsed = parse_import_file_name(file_name)
        if None is parsed:
            return True, "", file_name
        return False, parsed.started_at.isoformat(), file_name

    return sorted(file_names, key=sort_key)
