"""Turning one CSV row into a record's natural key and content.

A row carries only its file's columns: `content` holds a field for
each of them and nothing for the others, so importing a file never
clears what another file's extra columns stored (DOMAIN_MODEL §5.4).
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

from data_reaper.domain.exceptions import InvalidRowException
from data_reaper.domain.model.constants import (
    EVENTS_DATASET,
    PLACES_DATASET,
    REQUIRED_COLUMNS,
)
from data_reaper.domain.rules.row_values import (
    parse_boolean,
    parse_datetime,
    parse_float,
    parse_integer,
    parse_location,
    parse_text,
    parse_text_list,
)

ValueParser = Callable[[str, str], Any]

MAX_RATING = 10.0
"""TheFork rates out of 10, Google out of 5; both are kept as shown."""

PLACE_FIELDS: dict[str, tuple[str, ValueParser]] = {
    "name": ("name", parse_text),
    "source_url": ("source_url", parse_text),
    "address": ("address", parse_text),
    "location": ("location", parse_location),
    "categories": ("categories", parse_text_list),
    "rating": ("rating", parse_float),
    "review_count": ("review_count", parse_integer),
    "price_range": ("price_range", parse_text),
    "website": ("website", parse_text),
    "phone": ("phone", parse_text),
    "opening_hours": ("opening_hours", parse_text_list),
}
"""Places column → (record field, parser); `item_id` is the key."""

EVENT_FIELDS: dict[str, tuple[str, ValueParser]] = {
    "name": ("name", parse_text),
    "source_url": ("source_url", parse_text),
    "start_date": ("start_date", parse_datetime),
    "end_date": ("end_date", parse_datetime),
    "timezone": ("timezone", parse_text),
    "all_day": ("is_all_day", parse_boolean),
    "venue": ("venue", parse_text),
    "address": ("address", parse_text),
    "categories": ("categories", parse_text_list),
    "organizers": ("organizers", parse_text_list),
    "cost": ("cost", parse_text),
    "price_min": ("price_min", parse_float),
    "price_max": ("price_max", parse_float),
    "image_url": ("image_url", parse_text),
}
"""Events column → (record field, parser); `item_id` is the key."""

DATASET_FIELDS: dict[str, dict[str, tuple[str, ValueParser]]] = {
    PLACES_DATASET: PLACE_FIELDS,
    EVENTS_DATASET: EVENT_FIELDS,
}

_NON_NEGATIVE_FIELDS = ("review_count", "price_min", "price_max")


@dataclass(frozen=True)
class NormalizedRow:
    """One row, ready to upsert.

    Attributes:
        source: The website it comes from, e.g. `thefork.es`: half of
            the natural key.
        item_id: The website's own id for the item: the other half.
        content: Record field → typed value, for the file's columns.
    """

    source: str
    item_id: str
    content: dict[str, Any]


def normalize_row(dataset: str, row: Mapping[str, str]) -> NormalizedRow:
    """Return the row's natural key and typed content.

    Columns of `row` the Dataset doesn't know are ignored; the header
    was checked when the Dataset was detected.

    Raises:
        InvalidRowException: a required value is empty, a value isn't
            of its column's type or is out of range, or `source_url`
            has no host.
    """
    content: dict[str, Any] = {}
    for column, (field_name, parse) in DATASET_FIELDS[dataset].items():
        if column in row:
            content[field_name] = parse(column, row[column] or "")
    item_id = parse_text("item_id", row.get("item_id") or "")
    _ensure_required({**content, "item_id": item_id})
    _ensure_in_range(content)
    return NormalizedRow(
        source=get_source_name(content["source_url"]),
        item_id=item_id,
        content=content,
    )


def get_source_name(source_url: str) -> str:
    """Return the website a URL belongs to: its host, without `www.`.

    `https://www.thefork.es/restaurante/…` → `thefork.es`, so the same
    restaurant crawled by two Crawlers of one site merges into one
    record, and the same id on two sites never does.

    Raises:
        InvalidRowException: the URL has no host.
    """
    host = (urlsplit(source_url).hostname or "").lower()
    if not host:
        raise InvalidRowException(f"source_url: no website in {source_url!r}.")
    return host.removeprefix("www.")


def _ensure_required(content: Mapping[str, Any]) -> None:
    """Refuse a row that leaves a required column empty.

    Raises:
        InvalidRowException: one is empty; the message names it.
    """
    for column in REQUIRED_COLUMNS:
        if None is content.get(column):
            raise InvalidRowException(f"{column}: required, but empty.")


def _ensure_in_range(content: Mapping[str, Any]) -> None:
    """Refuse counts and prices below 0, and ratings above 10.

    Raises:
        InvalidRowException: a value is out of range.
    """
    rating = content.get("rating")
    if None is not rating and not 0 <= rating <= MAX_RATING:
        raise InvalidRowException(f"rating: expected 0 to 10, got {rating}.")
    for name in _NON_NEGATIVE_FIELDS:
        _ensure_not_negative(name, content.get(name))


def _ensure_not_negative(name: str, value: float | None) -> None:
    """Refuse a count or price below 0.

    Raises:
        InvalidRowException: `value` is below 0.
    """
    if None is not value and value < 0:
        raise InvalidRowException(f"{name}: expected ≥ 0, got {value}.")
