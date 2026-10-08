from datetime import datetime

import pytest
from data_reaper.domain.exceptions import InvalidRowException
from data_reaper.domain.model.value_objects import GeoLocation
from data_reaper.domain.rules import row_values


@pytest.mark.parametrize(
    "parse",
    [
        row_values.parse_text,
        row_values.parse_float,
        row_values.parse_integer,
        row_values.parse_boolean,
        row_values.parse_datetime,
        row_values.parse_location,
    ],
)
def test_an_empty_cell_is_none(parse):
    assert None is parse("column", "  ")


def test_an_empty_list_cell_is_an_empty_list():
    assert [] == row_values.parse_text_list("categories", "")


def test_text_is_unescaped_and_trimmed():
    assert "Jueves – Club €" == row_values.parse_text(
        "name", " Jueves &#8211; Club &euro; "
    )


def test_numbers_and_booleans_read_their_text():
    assert 9.8 == row_values.parse_float("rating", "9.8")
    assert 9.0 == row_values.parse_float("rating", "9")
    assert 45 == row_values.parse_integer("review_count", "45")
    assert row_values.parse_boolean("all_day", "True")
    assert not row_values.parse_boolean("all_day", "false")


@pytest.mark.parametrize(
    ("parse", "text"),
    [
        (row_values.parse_float, "nine"),
        (row_values.parse_float, "nan"),
        (row_values.parse_integer, "12.0"),
        (row_values.parse_boolean, "maybe"),
        (row_values.parse_datetime, "next friday"),
        (row_values.parse_location, "[1, 2]"),
        (row_values.parse_location, '{"latitude": 91, "longitude": 2}'),
        (row_values.parse_location, '{"latitude": true, "longitude": 2}'),
        (row_values.parse_text_list, '{"a": 1}'),
        (row_values.parse_text_list, "[broken"),
    ],
)
def test_a_value_of_the_wrong_type_is_rejected_naming_its_column(parse, text):
    with pytest.raises(InvalidRowException) as exc_info:
        parse("column", text)

    assert 422 == exc_info.value.status_code
    assert exc_info.value.message.startswith("column: expected")


def test_a_long_bad_value_is_cut_in_the_reason():
    with pytest.raises(InvalidRowException) as exc_info:
        row_values.parse_float("rating", "x" * 100)

    assert "…" in exc_info.value.message
    assert len(exc_info.value.message) < 80


def test_datetimes_keep_their_wall_clock_time():
    assert datetime(2026, 10, 8, 20, 30) == row_values.parse_datetime(
        "start_date", "2026-10-08 20:30:00"
    )
    assert datetime(2026, 10, 8, 20, 30) == row_values.parse_datetime(
        "start_date", "2026-10-08T20:30:00+02:00"
    )


def test_text_lists_read_json_or_one_plain_text():
    assert ["Free", "In English"] == row_values.parse_text_list(
        "categories", '["Free", " ", "In English"]'
    )
    assert ["Failing In Love"] == row_values.parse_text_list(
        "categories", "Failing In Love"
    )
    assert ["A & B"] == row_values.parse_text_list("organizers", '["A &#038; B"]')


def test_a_location_is_a_point():
    assert GeoLocation(41.4, 2.15) == row_values.parse_location(
        "location", '{"latitude": 41.4, "longitude": 2.15}'
    )
