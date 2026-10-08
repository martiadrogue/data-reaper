import httpx
import pytest
from data_reaper import api_client


@pytest.fixture
def respond(monkeypatch):
    """Route the client through a handler; returns the requests seen."""
    seen: list[httpx.Request] = []

    def install(handler):
        def recording(request: httpx.Request) -> httpx.Response:
            seen.append(request)
            return handler(request)

        monkeypatch.setattr(api_client, "TRANSPORT", httpx.MockTransport(recording))
        return seen

    return install


@pytest.mark.anyio
async def test_requests_carry_the_token_and_return_json(respond):
    seen = respond(lambda request: httpx.Response(200, json=[{"name": "places"}]))

    datasets = await api_client.list_datasets("tok")

    assert [{"name": "places"}] == datasets
    assert "Bearer tok" == seen[0].headers["authorization"]
    assert "/api/datasets" == seen[0].url.path


@pytest.mark.anyio
async def test_api_errors_carry_the_backend_message(respond):
    respond(lambda request: httpx.Response(409, json={"message": "Nope."}))

    with pytest.raises(api_client.ApiError) as exc_info:
        await api_client.retry_import("tok", "i1")

    assert 409 == exc_info.value.status_code
    assert "Nope." == exc_info.value.message


@pytest.mark.anyio
async def test_validation_errors_are_flattened(respond):
    respond(
        lambda request: httpx.Response(
            422, json={"detail": [{"loc": ["query", "text"], "msg": "too long"}]}
        )
    )

    with pytest.raises(api_client.ApiError) as exc_info:
        await api_client.list_places("tok", {"text": "x" * 200})

    assert "query.text: too long" == exc_info.value.message


@pytest.mark.anyio
async def test_a_non_json_error_keeps_its_text(respond):
    respond(lambda request: httpx.Response(502, text="Bad gateway"))

    with pytest.raises(api_client.ApiError) as exc_info:
        await api_client.list_events("tok", {})

    assert "Bad gateway" == exc_info.value.message


@pytest.mark.anyio
async def test_empty_responses_are_none_and_none_params_are_dropped(respond):
    seen = respond(lambda request: httpx.Response(204))

    result = await api_client.list_imports(
        "tok", {"status": None, "limit": 50, "offset": 0}
    )

    assert None is result
    assert {"limit": "50", "offset": "0"} == dict(seen[0].url.params)


ENDPOINTS = [
    (api_client.list_datasets, ("tok",), "GET", "/api/datasets"),
    (api_client.list_imports, ("tok", {}), "GET", "/api/dataset-imports"),
    (api_client.get_import, ("tok", "i1"), "GET", "/api/dataset-imports/i1"),
    (api_client.scan_imports, ("tok",), "POST", "/api/dataset-imports/scan"),
    (
        api_client.retry_import,
        ("tok", "i1"),
        "POST",
        "/api/dataset-imports/i1/retry",
    ),
    (api_client.list_places, ("tok", {}), "GET", "/api/places"),
    (api_client.list_events, ("tok", {}), "GET", "/api/events"),
]


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("call", "args", "method", "path"),
    ENDPOINTS,
    ids=[endpoint[0].__name__ for endpoint in ENDPOINTS],
)
async def test_each_call_hits_its_endpoint(respond, call, args, method, path):
    seen = respond(lambda request: httpx.Response(200, json={"id": "x"}))

    await call(*args)

    assert (method, path) == (seen[0].method, seen[0].url.path)


@pytest.mark.anyio
async def test_ids_are_escaped_in_paths(respond):
    seen = respond(lambda request: httpx.Response(200, json={"id": "x"}))

    await api_client.get_import("tok", "a/b")

    assert "/api/dataset-imports/a%2Fb" == seen[0].url.raw_path.decode()


@pytest.mark.anyio
async def test_list_places_sends_only_the_filters_set(respond):
    page = {"items": [], "limit": 50, "offset": 0, "total": 0, "has_more": False}
    seen = respond(lambda request: httpx.Response(200, json=page))

    listed = await api_client.list_places(
        "tok", {"text": "grill", "source": None, "limit": 50, "offset": 0}
    )

    assert page == listed
    assert {"text": "grill", "limit": "50", "offset": "0"} == dict(seen[0].url.params)
