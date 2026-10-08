"""Use cases for browsing what the imports stored: places and events."""

from data_reaper.domain.bundles.record_query import RecordQuery
from data_reaper.domain.exceptions import ValidationException
from data_reaper.domain.model.constants import (
    DATASET_COLLECTIONS,
    DATASET_COLUMNS,
)
from data_reaper.domain.ports.repository_sets import (
    AbstractReadRepositories,
)
from data_reaper.domain.rules.pagination import MAX_PAGE_SIZE, resolve_page
from data_reaper.schemas.dataset import DatasetOut
from data_reaper.schemas.dataset_event import EventOut, EventsPageOut
from data_reaper.schemas.dataset_place import PlaceOut, PlacesPageOut
from data_reaper.schemas.dataset_record import DatasetRecordQuery


async def get_datasets(read_repositories: AbstractReadRepositories) -> list[DatasetOut]:
    """Return every Dataset with its columns and records per source."""
    datasets = []
    for name, collection in DATASET_COLLECTIONS.items():
        repository = getattr(read_repositories, collection)
        source_counts = await repository.count_by_source()
        datasets.append(
            DatasetOut(
                name=name,
                collection=collection,
                columns=list(DATASET_COLUMNS[name]),
                record_count=sum(source_counts.values()),
                source_counts=source_counts,
            )
        )
    return datasets


async def get_places(
    read_repositories: AbstractReadRepositories,
    query: DatasetRecordQuery,
    limit: int = MAX_PAGE_SIZE,
    offset: int = 0,
) -> PlacesPageOut:
    """Return one page of places, by name, and how many match.

    A filtered listing returns one capped page; an unfiltered one
    pages up to a hard total (`domain/rules/pagination.py`).
    """
    record_query = RecordQuery(text=query.text, source=query.source)
    page_limit, page_offset = resolve_page(record_query.has_filters, limit, offset)
    repository = read_repositories.dataset_places
    places = await repository.get_all(record_query, page_limit + 1, page_offset)
    return PlacesPageOut(
        items=[PlaceOut.model_validate(place) for place in places[:page_limit]],
        limit=page_limit,
        offset=page_offset,
        total=await repository.count_all(record_query),
        has_more=len(places) > page_limit,
    )


async def get_place(
    read_repositories: AbstractReadRepositories, place_id: str
) -> PlaceOut:
    """Return one place.

    Raises:
        ValidationException: it does not exist (404).
    """
    place = await read_repositories.dataset_places.get_by_id(place_id)
    if None is place:
        raise ValidationException("Place not found.", 404)
    return PlaceOut.model_validate(place)


async def get_events(
    read_repositories: AbstractReadRepositories,
    query: DatasetRecordQuery,
    limit: int = MAX_PAGE_SIZE,
    offset: int = 0,
) -> EventsPageOut:
    """Return one page of events, by name, and how many match.

    Pages like `get_places`.
    """
    record_query = RecordQuery(text=query.text, source=query.source)
    page_limit, page_offset = resolve_page(record_query.has_filters, limit, offset)
    repository = read_repositories.dataset_events
    events = await repository.get_all(record_query, page_limit + 1, page_offset)
    return EventsPageOut(
        items=[EventOut.model_validate(event) for event in events[:page_limit]],
        limit=page_limit,
        offset=page_offset,
        total=await repository.count_all(record_query),
        has_more=len(events) > page_limit,
    )


async def get_event(
    read_repositories: AbstractReadRepositories, event_id: str
) -> EventOut:
    """Return one event.

    Raises:
        ValidationException: it does not exist (404).
    """
    event = await read_repositories.dataset_events.get_by_id(event_id)
    if None is event:
        raise ValidationException("Event not found.", 404)
    return EventOut.model_validate(event)
