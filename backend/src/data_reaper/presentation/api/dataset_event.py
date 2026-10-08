"""Routes for browsing events (`dataset_events`)."""

from data_reaper.domain.ports.repository_sets import (
    AbstractReadRepositories,
)
from data_reaper.presentation.api.dependencies import (
    get_current_user,
    get_read_repositories,
)
from data_reaper.schemas.auth import UserOut
from data_reaper.schemas.dataset_event import EventOut, EventsPageOut
from data_reaper.schemas.dataset_record import DatasetRecordQuery
from data_reaper.services import dataset_record_service
from fastapi import Depends, Query
from fastapi.routing import APIRouter

router = APIRouter(prefix="/api/events", tags=["Events"])


@router.get("", response_model=EventsPageOut)
async def get_events(
    query: DatasetRecordQuery = Depends(),
    limit: int = Query(default=50, ge=1, le=50),
    offset: int = Query(default=0, ge=0, le=250),
    read_repositories: AbstractReadRepositories = Depends(get_read_repositories),
    _: UserOut = Depends(get_current_user),
) -> EventsPageOut:
    """List events by name, with the total that match.

    Filtered by `text` (part of the name or address, any case) or
    `source` (e.g. `atrapalo.com`), it is one page of up to 50;
    unfiltered, it paginates up to 300 events deep.
    """
    return await dataset_record_service.get_events(
        read_repositories, query, limit=limit, offset=offset
    )


@router.get("/{event_id}", response_model=EventOut)
async def get_event(
    event_id: str,
    read_repositories: AbstractReadRepositories = Depends(get_read_repositories),
    _: UserOut = Depends(get_current_user),
) -> EventOut:
    """Get one event.

    Raises:
        ValidationException: 404 if it is missing.
    """
    return await dataset_record_service.get_event(read_repositories, event_id)
