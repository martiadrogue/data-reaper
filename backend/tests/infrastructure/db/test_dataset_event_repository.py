from datetime import datetime

import pytest
from data_reaper.domain.bundles.record_query import RecordQuery
from data_reaper.domain.exceptions import ValidationException
from data_reaper.domain.model.entities import DatasetEvent

NOW = datetime(2026, 10, 5, 10)


def _event(event_id: str, item_id: str, **overrides) -> DatasetEvent:
    return DatasetEvent(
        **{
            "id": event_id,
            "source": "atrapalo.com",
            "item_id": item_id,
            "name": f"Show {item_id}",
            "source_url": f"https://www.atrapalo.com/entradas/{item_id}",
            "content_hash": "hash",
            "created_at": NOW,
            "updated_at": NOW,
            "last_seen_at": NOW,
            **overrides,
        }
    )


@pytest.mark.anyio
async def test_events_round_trip_with_their_dates(write_repositories):
    repository = write_repositories.dataset_events
    saved = await repository.save_all(
        [
            _event(
                "e1",
                "s1",
                start_date=datetime(2026, 10, 8, 19, 30),
                is_all_day=False,
                organizers=["Berto Romero"],
            )
        ]
    )

    assert saved == [await repository.get_by_id("e1")]
    assert 1 == await repository.count_all(RecordQuery(source="atrapalo.com"))


@pytest.mark.anyio
async def test_the_validator_refuses_a_negative_price(write_repositories):
    with pytest.raises(ValidationException) as exc_info:
        await write_repositories.dataset_events.save_all(
            [_event("e1", "s1", price_min=-1.0)]
        )

    assert 400 == exc_info.value.status_code
