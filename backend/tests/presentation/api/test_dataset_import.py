from datetime import datetime

import pytest
from csv_samples import PLACES_HEADER, file_name, place_line


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("POST", "/api/dataset-imports/scan"),
        ("POST", "/api/dataset-imports/import-1/retry"),
    ],
)
async def test_scanning_and_retrying_are_admin_only(client, act_as, method, path):
    act_as("member")

    response = await client.request(method, path)

    assert 403 == response.status_code


@pytest.mark.anyio
async def test_listing_imports_needs_a_login(client):
    response = await client.get("/api/dataset-imports")

    assert 401 == response.status_code


@pytest.mark.anyio
async def test_an_admin_scans_and_anyone_follows_the_imports(
    client, act_as, file_storage, import_dispatcher
):
    file_storage.add(file_name(1), PLACES_HEADER, place_line("r1"))
    act_as("admin")

    scanned = await client.post("/api/dataset-imports/scan")
    act_as("member")
    listed = await client.get("/api/dataset-imports", params={"status": "pending"})
    import_id = scanned.json()["imports_created"][0]["id"]
    fetched = await client.get(f"/api/dataset-imports/{import_id}")

    assert 202 == scanned.status_code
    assert 1 == scanned.json()["files_found"]
    assert [import_id] == import_dispatcher.dispatched
    assert 200 == listed.status_code
    assert {"pending": 1} == listed.json()["status_counts"]
    assert file_name(1) == fetched.json()["file_name"]
    assert 0 == fetched.json()["metrics"]["rows_read"]


@pytest.mark.anyio
async def test_an_unknown_status_filter_is_refused(client, act_as):
    act_as("member")

    response = await client.get("/api/dataset-imports", params={"status": "done"})

    assert 422 == response.status_code


@pytest.mark.anyio
async def test_retrying_an_unknown_import_is_404(client, act_as):
    act_as("admin")

    response = await client.post("/api/dataset-imports/missing/retry")

    assert 404 == response.status_code
    assert "Dataset import not found." == response.json()["message"]


@pytest.mark.anyio
async def test_field_changes_come_most_changed_first(client, act_as, mongo_database):
    client_db, database_name = mongo_database
    now = datetime(2026, 10, 5, 10)
    await client_db[database_name]["dataset_imports"].insert_one(
        {
            "_id": "i1",
            "file_name": "a.csv",
            "status": "imported",
            "created_at": now,
            "updated_at": now,
            "field_changes": {"phone": 2, "rating": 5, "name": 2},
        }
    )
    act_as("member")

    fetched = await client.get("/api/dataset-imports/i1")
    listed = await client.get("/api/dataset-imports")

    expected = [
        {"field": "rating", "count": 5},
        {"field": "name", "count": 2},
        {"field": "phone", "count": 2},
    ]
    assert expected == fetched.json()["field_changes"]
    assert expected == listed.json()["items"][0]["field_changes"]
