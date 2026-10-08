from datetime import datetime

import pytest
from data_reaper.domain.bundles.record_query import RecordQuery
from data_reaper.domain.exceptions import ValidationException
from data_reaper.domain.model.entities import DatasetPlace
from data_reaper.domain.model.value_objects import GeoLocation

NOW = datetime(2026, 10, 5, 10)


def _place(place_id: str, item_id: str, **overrides) -> DatasetPlace:
    return DatasetPlace(
        **{
            "id": place_id,
            "source": "thefork.es",
            "item_id": item_id,
            "name": f"Place {item_id}",
            "source_url": f"https://www.thefork.es/r/{item_id}",
            "content_hash": "hash",
            "created_at": NOW,
            "updated_at": NOW,
            "last_seen_at": NOW,
            **overrides,
        }
    )


@pytest.mark.anyio
async def test_save_all_replaces_by_id_and_the_location_round_trips(
    write_repositories,
):
    repository = write_repositories.dataset_places
    located = _place("p1", "r1", location=GeoLocation(41.4, 2.15))
    await repository.save_all([located, _place("p2", "r2")])
    await repository.save_all([_place("p2", "r2", name="Renamed")])

    assert located == await repository.get_by_id("p1")
    assert "Renamed" == (await repository.get_by_id("p2")).name
    assert 2 == await repository.count_all(RecordQuery())


@pytest.mark.anyio
async def test_save_all_of_nothing_writes_nothing(write_repositories):
    assert [] == await write_repositories.dataset_places.save_all([])


@pytest.mark.anyio
async def test_a_natural_key_has_one_record(write_repositories):
    repository = write_repositories.dataset_places
    await repository.save_all([_place("p1", "r1")])

    with pytest.raises(ValidationException) as exc_info:
        await repository.save_all([_place("p2", "r1")])

    assert 409 == exc_info.value.status_code


@pytest.mark.anyio
async def test_the_same_item_id_on_two_sources_is_two_records(write_repositories):
    repository = write_repositories.dataset_places
    await repository.save_all(
        [_place("p1", "r1"), _place("p2", "r1", source="maps.google.com")]
    )

    found = await repository.get_all_by_item_ids("thefork.es", ["r1", "missing"])

    assert ["p1"] == [place.id for place in found]
    assert {"thefork.es": 1, "maps.google.com": 1} == (
        await repository.count_by_source()
    )


@pytest.mark.anyio
async def test_listing_matches_name_or_address_literally(write_repositories):
    repository = write_repositories.dataset_places
    await repository.save_all(
        [
            _place("p1", "r1", name="Grill (Gràcia)"),
            _place("p2", "r2", name="Bar", address="Carrer del Grill"),
            _place("p3", "r3", name="Café", source="maps.google.com"),
        ]
    )

    by_text = await repository.get_all(RecordQuery(text="grill"))
    literal = await repository.get_all(RecordQuery(text="(gràcia)"))
    by_source = await repository.get_all(RecordQuery(source="maps.google.com"))

    assert ["p2", "p1"] == [place.id for place in by_text]
    assert ["p1"] == [place.id for place in literal]
    assert ["p3"] == [place.id for place in by_source]


@pytest.mark.anyio
async def test_the_validator_refuses_a_rating_above_ten(write_repositories):
    with pytest.raises(ValidationException) as exc_info:
        await write_repositories.dataset_places.save_all(
            [_place("p1", "r1", rating=11.0)]
        )

    assert 400 == exc_info.value.status_code
