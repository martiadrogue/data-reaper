from datetime import datetime

import pytest


@pytest.mark.anyio
async def test_events_list_and_get(client, act_as, insert_record):
    await insert_record(
        "dataset_events",
        _id="e1",
        source="atrapalo.com",
        item_id="s1",
        name="Show",
        organizers=["Berto Romero"],
        start_date=datetime(2026, 10, 8, 19, 30),
    )
    act_as("member")

    listed = await client.get("/api/events", params={"source": "atrapalo.com"})
    fetched = await client.get("/api/events/e1")

    assert ["e1"] == [item["id"] for item in listed.json()["items"]]
    assert "2026-10-08T19:30:00" == fetched.json()["start_date"]
    assert ["Berto Romero"] == fetched.json()["organizers"]


@pytest.mark.anyio
async def test_an_unknown_event_is_404(client, act_as):
    act_as("member")

    assert 404 == (await client.get("/api/events/missing")).status_code


@pytest.mark.anyio
async def test_paging_is_capped_like_every_listing(client, act_as):
    act_as("member")

    response = await client.get("/api/events", params={"offset": 251})

    assert 422 == response.status_code
