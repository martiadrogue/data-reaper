"""Turning one CSV cell's text into a typed value.

Every parser returns `None` (`[]` for lists) for an empty cell, since
missing data is not an error (CONTRIBUTING R1.6.7), and raises
`InvalidRowException` naming the column for a value of the wrong type.
Text is HTML-unescaped and trimmed: crawled values often keep entities
such as `&#8211;` or `&euro;`.
"""

import html
import json
import math
from datetime import datetime
from typing import Any

from data_reaper.domain.exceptions import InvalidRowException
from data_reaper.domain.model.value_objects import GeoLocation

_SHOWN_VALUE_LENGTH = 40
_TRUE_TEXTS = frozenset({"true", "1", "yes"})
_FALSE_TEXTS = frozenset({"false", "0", "no"})


def parse_text(column: str, text: str) -> str | None:
    """Return the cell as clean text, or `None` when empty."""
    value = html.unescape(text).strip()
    return value or None


def parse_float(column: str, text: str) -> float | None:
    """Return the cell as a finite float.

    Raises:
        InvalidRowException: the cell isn't a finite number.
    """
    value = text.strip()
    if not value:
        return None
    try:
        number = float(value)
    except ValueError as error:
        raise _type_error(column, "a number", value) from error
    if not math.isfinite(number):
        raise _type_error(column, "a number", value)
    return number


def parse_integer(column: str, text: str) -> int | None:
    """Return the cell as an integer; `"12.0"` is not one.

    Raises:
        InvalidRowException: the cell isn't a whole number.
    """
    value = text.strip()
    if not value:
        return None
    try:
        return int(value)
    except ValueError as error:
        raise _type_error(column, "a whole number", value) from error


def parse_boolean(column: str, text: str) -> bool | None:
    """Return the cell as a boolean: true/false, 1/0, or yes/no.

    Raises:
        InvalidRowException: the cell is none of those, in any case.
    """
    value = text.strip().lower()
    if not value:
        return None
    if value in _TRUE_TEXTS:
        return True
    if value in _FALSE_TEXTS:
        return False
    raise _type_error(column, "true or false", text.strip())


def parse_datetime(column: str, text: str) -> datetime | None:
    """Return the cell as a naive datetime, its wall-clock time kept.

    Takes ISO 8601 (`2026-10-08 20:30:00` or with a `T`). An offset,
    if any, is dropped without converting: the row's `timezone`
    column says where the time is read.

    Raises:
        InvalidRowException: the cell isn't an ISO 8601 date and time.
    """
    value = text.strip()
    if not value:
        return None
    try:
        return datetime.fromisoformat(value).replace(tzinfo=None)
    except ValueError as error:
        raise _type_error(column, "a date and time", value) from error


def parse_text_list(column: str, text: str) -> list[str]:
    """Return the cell as a list of texts.

    A JSON list is read element by element (blank ones dropped); any
    other non-empty text is a list of that one text.

    Raises:
        InvalidRowException: the cell starts as JSON but isn't a list.
    """
    value = text.strip()
    if not value:
        return []
    if not value.startswith(("[", "{")):
        return [html.unescape(value).strip()]
    elements = _load_json(column, value)
    if not isinstance(elements, list):
        raise _type_error(column, "a list", value)
    return _clean_texts(elements)


def _clean_texts(elements: list[Any]) -> list[str]:
    """Return each element as clean text, blank ones dropped."""
    texts = (html.unescape(str(element)).strip() for element in elements)
    return [text for text in texts if text]


def parse_location(column: str, text: str) -> GeoLocation | None:
    """Return the cell, `{"latitude": …, "longitude": …}`, as a point.

    Raises:
        InvalidRowException: the cell isn't such an object, or a
            coordinate is out of range.
    """
    value = text.strip()
    if not value:
        return None
    point = _load_json(column, value)
    if not isinstance(point, dict):
        raise _type_error(column, "a latitude and longitude", value)
    latitude = _read_coordinate(column, point.get("latitude"), 90)
    longitude = _read_coordinate(column, point.get("longitude"), 180)
    return GeoLocation(latitude=latitude, longitude=longitude)


def _read_coordinate(column: str, value: Any, limit: float) -> float:
    """Return a coordinate within ±`limit` degrees.

    Raises:
        InvalidRowException: it is missing, not a number, or out of
            range.
    """
    is_number = isinstance(value, int | float) and not isinstance(value, bool)
    if not is_number or not math.isfinite(value) or abs(value) > limit:
        raise _type_error(column, "a latitude and longitude", str(value))
    return float(value)


def _load_json(column: str, value: str) -> Any:
    """Decode the cell's JSON.

    Raises:
        InvalidRowException: the cell isn't valid JSON.
    """
    try:
        return json.loads(value)
    except ValueError as error:
        raise _type_error(column, "valid JSON", value) from error


def _type_error(column: str, expected: str, value: str) -> InvalidRowException:
    """Return the rejection for a value that isn't of its type."""
    shown = value[:_SHOWN_VALUE_LENGTH]
    if len(value) > _SHOWN_VALUE_LENGTH:
        shown += "…"
    return InvalidRowException(f"{column}: expected {expected}, got {shown!r}.")
