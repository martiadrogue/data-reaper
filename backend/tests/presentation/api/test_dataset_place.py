import pytest


@pytest.mark.anyio
async def test_places_list_and_get_with_their_location(client, act_as, insert_record):
    await insert_record(
        "dataset_places",
        _id="p1",
        item_id="r1",
        name="Arrabal",
        location={"latitude": 41.4, "longitude": 2.15},
        opening_hours=[],
        rating=9.8,
    )
    act_as("member")

    listed = await client.get("/api/places", params={"text": "arra"})
    fetched = await client.get("/api/places/p1")

    assert 200 == listed.status_code
    assert (1, "Arrabal") == (listed.json()["total"], listed.json()["items"][0]["name"])
    assert {"latitude": 41.4, "longitude": 2.15} == fetched.json()["location"]
    assert None is fetched.json()["phone"]


@pytest.mark.anyio
async def test_an_unknown_place_is_404(client, act_as):
    act_as("member")

    assert 404 == (await client.get("/api/places/missing")).status_code


@pytest.mark.anyio
async def test_paging_is_capped_like_every_listing(client, act_as):
    act_as("member")

    response = await client.get("/api/places", params={"limit": 51})

    assert 422 == response.status_code
