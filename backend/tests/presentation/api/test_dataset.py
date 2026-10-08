import pytest


@pytest.mark.anyio
@pytest.mark.parametrize(
    "path", ["/api/datasets", "/api/places", "/api/events", "/api/places/p1"]
)
async def test_browsing_needs_a_login(client, path):
    response = await client.get(path)

    assert 401 == response.status_code


@pytest.mark.anyio
async def test_datasets_describe_both_collections(client, act_as):
    act_as("member")

    response = await client.get("/api/datasets")

    assert ["places", "events"] == [item["name"] for item in response.json()]
    assert ["dataset_places", "dataset_events"] == [
        item["collection"] for item in response.json()
    ]
