"""Which Dataset a CSV belongs to, decided from its header alone."""

from collections.abc import Sequence

from data_reaper.domain.exceptions import ValidationException
from data_reaper.domain.model.constants import (
    DATASET_COLUMNS,
    REQUIRED_COLUMNS,
)


def detect_dataset(columns: Sequence[str]) -> str:
    """Return the one Dataset whose columns include every header column.

    A file may hold any subset of its Dataset's columns, as long as the
    required ones are there.

    Raises:
        ValidationException: the header repeats a column, lacks a
            required one, has a column no Dataset knows, or fits more
            than one Dataset (422). The message says which.
    """
    _ensure_no_repeats(columns)
    _ensure_required_columns(columns)
    header = set(columns)
    matches = [
        dataset
        for dataset, dataset_columns in DATASET_COLUMNS.items()
        if header <= set(dataset_columns)
    ]
    if not matches:
        raise _explain_no_match(columns)
    if 1 < len(matches):
        raise ValidationException(
            "The columns fit more than one dataset ("
            + ", ".join(matches)
            + "); add a column only one of them has.",
            422,
        )
    return matches[0]


def _explain_no_match(columns: Sequence[str]) -> ValidationException:
    """Return why no Dataset holds every column of the header."""
    unknown = sorted(set(columns) - _all_known_columns())
    if unknown:
        return ValidationException(f"Unknown columns: {', '.join(unknown)}.", 422)
    return ValidationException(
        "The columns mix more than one dataset: " + ", ".join(columns) + ".", 422
    )


def _ensure_no_repeats(columns: Sequence[str]) -> None:
    """Refuse a header that repeats a column.

    Raises:
        ValidationException: a column is repeated (422).
    """
    repeated = sorted({column for column in columns if 1 < columns.count(column)})
    if repeated:
        raise ValidationException(f"Repeated columns: {', '.join(repeated)}.", 422)


def _ensure_required_columns(columns: Sequence[str]) -> None:
    """Refuse a header without every required column.

    Raises:
        ValidationException: a required column is missing (422).
    """
    missing = [column for column in REQUIRED_COLUMNS if column not in columns]
    if missing:
        raise ValidationException(
            f"Missing required columns: {', '.join(missing)}.", 422
        )


def _all_known_columns() -> set[str]:
    """Return every column of every Dataset."""
    return {column for columns in DATASET_COLUMNS.values() for column in columns}
