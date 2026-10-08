from datetime import datetime

import pytest
from data_reaper.domain.exceptions import InvalidRowException
from data_reaper.domain.model.value_objects import GeoLocation
from data_reaper.domain.rules.dataset_rows import (
    get_source_name,
    normalize_row,
)

PLACE = {
    "item_id": "ba9c4a16",
    "name": "Arrabal",
    "location": '{"latitude": 41.4, "longitude": 2.15}',
    "categories": '["Argentino"]',
    "rating": "9.8",
    "review_count": "45",
    "price_range": "3",
    "source_url": "https://www.thefork.es/restaurante/arrabal-r868945",
}


def test_a_place_row_gets_its_natural_key_and_typed_content():
    row = normalize_row("places", PLACE)

    assert ("thefork.es", "ba9c4a16") == (row.source, row.item_id)
    assert {
        "name": "Arrabal",
        "source_url": PLACE["source_url"],
        "location": GeoLocation(41.4, 2.15),
        "categories": ["Argentino"],
        "rating": 9.8,
        "review_count": 45,
        "price_range": "3",
    } == row.content


def test_only_the_files_columns_are_in_the_content():
    row = normalize_row("places", PLACE)

    assert "address" not in row.content
    assert "opening_hours" not in row.content


def test_an_empty_cell_is_none_in_the_content():
    row = normalize_row("places", {**PLACE, "rating": ""})

    assert None is row.content["rating"]


def test_an_event_row_stores_all_day_as_is_all_day():
    row = normalize_row(
        "events",
        {
            "item_id": "29064",
            "name": "Coming In Hot",
            "start_date": "2026-10-05 19:30:00",
            "all_day": "False",
            "source_url": "https://thecomedyclubhouse.es/event/coming-in-hot-5/",
        },
    )

    assert "thecomedyclubhouse.es" == row.source
    assert False is row.content["is_all_day"]
    assert datetime(2026, 10, 5, 19, 30) == row.content["start_date"]


@pytest.mark.parametrize(
    ("changes", "reason"),
    [
        ({"item_id": " "}, "item_id: required, but empty."),
        ({"name": ""}, "name: required, but empty."),
        ({"rating": "11"}, "rating: expected 0 to 10, got 11.0."),
        ({"review_count": "-1"}, "review_count: expected ≥ 0, got -1."),
        ({"rating": "high"}, "rating: expected a number, got 'high'."),
        ({"source_url": "not a url"}, "source_url: no website in 'not a url'."),
    ],
)
def test_a_bad_row_is_rejected_with_its_reason(changes, reason):
    with pytest.raises(InvalidRowException) as exc_info:
        normalize_row("places", {**PLACE, **changes})

    assert reason == exc_info.value.message


def test_the_source_is_the_host_without_www():
    assert "thefork.es" == get_source_name("https://WWW.TheFork.es/r/1?x=1")
    assert "maps.google.com" == get_source_name("https://maps.google.com/?cid=1")
