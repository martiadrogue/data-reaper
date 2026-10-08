"""Server-side HTTP client for the Data Reaper API.

Every call runs inside a Reflex event handler on the Reflex backend,
never in the browser: the browser only talks to Reflex over its state
websocket, so the API needs no CORS setup.
"""

import os
from typing import Any
from urllib.parse import quote

import httpx

API_BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:8000")
TIMEOUT_SECONDS = 15.0
TRANSPORT: httpx.AsyncBaseTransport | None = None
"""Replaced in tests with `httpx.MockTransport`; `None` uses the network."""


class ApiError(Exception):
    """A non-2xx response, with the API's message."""

    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message
        super().__init__(f"{status_code}: {message}")


def _extract_message(status_code: int, body: object, raw_text: str) -> str:
    fallback = raw_text or f"Request failed with status {status_code}"
    if not isinstance(body, dict):
        return fallback
    # The API's own errors: {"message": "..."} (api/exception_handler.py).
    if "message" in body:
        return str(body["message"])
    # FastAPI request validation: {"detail": [{"loc": [...], "msg": ...}]}.
    if "detail" in body:
        return _detail_message(body["detail"])
    return fallback


def _detail_message(detail: object) -> str:
    """Return FastAPI's `detail`, joining validation errors."""
    if not isinstance(detail, list):
        return str(detail)
    return "; ".join(
        f"{'.'.join(str(part) for part in item.get('loc', []))}: {item.get('msg', '')}"
        for item in detail
    )


async def _request(
    method: str,
    path: str,
    *,
    token: str | None = None,
    json: object | None = None,
    params: dict | None = None,
) -> Any:
    response = await _send(method, path, token=token, json=json, params=params)
    return response.json() if response.content else None


async def _send(
    method: str,
    path: str,
    *,
    token: str | None = None,
    json: object | None = None,
    params: dict | None = None,
) -> httpx.Response:
    """Send one request and return the response, raising on errors."""
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    async with httpx.AsyncClient(
        base_url=API_BASE_URL, timeout=TIMEOUT_SECONDS, transport=TRANSPORT
    ) as client:
        response = await client.request(
            method,
            path,
            json=json,
            params=_query(params),
            headers=headers,
        )
    _raise_for_status(response)
    return response


def _query(params: dict | None) -> dict:
    """Return the query parameters, leaving out the unset ones."""
    return {key: value for key, value in (params or {}).items() if value is not None}


def _raise_for_status(response: httpx.Response) -> None:
    """Raise `ApiError` with the API's message for a non-2xx response."""
    if response.status_code < 400:
        return
    try:
        body = response.json()
    except ValueError:
        body = None
    raise ApiError(
        response.status_code,
        _extract_message(response.status_code, body, response.text),
    )


# --- Datasets and imports ---------------------------------------------------
async def list_datasets(token: str) -> list[dict]:
    return await _request("GET", "/api/datasets", token=token)


async def list_imports(token: str, params: dict) -> dict:
    """Return one page of imports; `params` holds status, limit, offset."""
    return await _request("GET", "/api/dataset-imports", token=token, params=params)


async def get_import(token: str, import_id: str) -> dict:
    return await _request(
        "GET", f"/api/dataset-imports/{quote(import_id, safe='')}", token=token
    )


async def scan_imports(token: str) -> dict:
    return await _request("POST", "/api/dataset-imports/scan", token=token)


async def retry_import(token: str, import_id: str) -> dict:
    return await _request(
        "POST",
        f"/api/dataset-imports/{quote(import_id, safe='')}/retry",
        token=token,
    )


# --- Dataset records ---------------------------------------------------------
async def list_places(token: str, params: dict) -> dict:
    """Return one page of places; `params` holds text, source, paging."""
    return await _request("GET", "/api/places", token=token, params=params)


async def list_events(token: str, params: dict) -> dict:
    """Return one page of events; `params` holds text, source, paging."""
    return await _request("GET", "/api/events", token=token, params=params)
