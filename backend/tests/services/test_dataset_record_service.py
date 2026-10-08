from datetime import datetime

import pytest
from data_reaper.domain.exceptions import ValidationException
from data_reaper.domain.model.entities import DatasetEvent, DatasetPlace
from data_reaper.domain.model.value_objects import GeoLocation
from data_reaper.schemas.dataset_record import DatasetRecordQuery
from data_reaper.services import dataset_record_service

NOW = datetime(2026, 10, 5, 10)
TRACKING = {
    "content_hash": "hash",
    "created_at": NOW,
    "updated_at": NOW,
    "last_seen_at": NOW,
}


def _place(number: int, source: str = "thefork.es") -> DatasetPlace:
    return DatasetPlace(
        id=f"p{number}",
        source=source,
        item_id=f"r{number}",
        name=f"Place {number:03d}",
        source_url=f"https://{source}/r{number}",
        location=GeoLocation(41.4, 2.15),
        **TRACKING,
    )


async def _seed_places(write_repositories, places):
    await write_repositories.dataset_places.save_all(places)
    await write_repositories.commit()


@pytest.mark.anyio
async def test_places_page_by_name_with_the_total(
    write_repositories, read_repositories
):
    await _seed_places(write_repositories, [_place(n) for n in range(60)])

    first = await dataset_record_service.get_places(
        read_repositories, DatasetRecordQuery()
    )
    second = await dataset_record_service.get_places(
        read_repositories, DatasetRecordQuery(), offset=50
    )

    assert (50, 60, True) == (len(first.items), first.total, first.has_more)
    assert "Place 000" == first.items[0].name
    assert (10, False) == (len(second.items), second.has_more)
    assert 41.4 == first.items[0].location.latitude


@pytest.mark.anyio
async def test_a_filtered_listing_is_one_page_from_the_top(
    write_repositories, read_repositories
):
    await _seed_places(
        write_repositories,
        [_place(1), _place(2, source="maps.google.com")],
    )

    page = await dataset_record_service.get_places(
        read_repositories, DatasetRecordQuery(source="maps.google.com"), offset=100
    )

    assert (0, 1, ["p2"]) == (page.offset, page.total, [p.id for p in page.items])


@pytest.mark.anyio
async def test_events_list_like_places(write_repositories, read_repositories):
    await write_repositories.dataset_events.save_all(
        [
            DatasetEvent(
                id="e1",
                source="atrapalo.com",
                item_id="s1",
                name="Show",
                source_url="https://www.atrapalo.com/s1",
                start_date=datetime(2026, 10, 8, 19, 30),
                **TRACKING,
            )
        ]
    )
    await write_repositories.commit()

    page = await dataset_record_service.get_events(
        read_repositories, DatasetRecordQuery(text="sho")
    )
    event = await dataset_record_service.get_event(read_repositories, "e1")

    assert ["e1"] == [item.id for item in page.items]
    assert datetime(2026, 10, 8, 19, 30) == event.start_date


@pytest.mark.anyio
async def test_datasets_count_records_per_source(write_repositories, read_repositories):
    await _seed_places(
        write_repositories, [_place(1), _place(2), _place(3, source="maps.google.com")]
    )

    datasets = await dataset_record_service.get_datasets(read_repositories)

    by_name = {dataset.name: dataset for dataset in datasets}
    assert 3 == by_name["places"].record_count
    assert {"thefork.es": 2, "maps.google.com": 1} == by_name["places"].source_counts
    assert "dataset_events" == by_name["events"].collection
    assert 0 == by_name["events"].record_count
    assert "start_date" in by_name["events"].columns


@pytest.mark.anyio
async def test_an_unknown_record_is_404(read_repositories):
    for get in (dataset_record_service.get_place, dataset_record_service.get_event):
        with pytest.raises(ValidationException) as exc_info:
            await get(read_repositories, "missing")
        assert 404 == exc_info.value.status_code
