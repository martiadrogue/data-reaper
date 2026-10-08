import pytest


@pytest.mark.anyio
async def test_cors_preflight_allows_the_frontend_origin(client):
    response = await client.options(
        "/api/dataset-imports/scan",
        headers={
            "Origin": "http://localhost:3100",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )

    assert 200 == response.status_code
    assert "http://localhost:3100" == response.headers["access-control-allow-origin"]
    assert "POST" in response.headers["access-control-allow-methods"]


@pytest.mark.anyio
async def test_cors_rejects_disallowed_origins(client):
    response = await client.options(
        "/api/dataset-imports/scan",
        headers={
            "Origin": "https://evil.example",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )

    assert 400 == response.status_code
    assert "access-control-allow-origin" not in response.headers
