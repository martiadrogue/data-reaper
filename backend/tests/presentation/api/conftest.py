from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import datetime

import httpx
import pytest
from data_reaper.core.di import REPOSITORY_FACTORIES
from data_reaper.domain.ports.repository_sets import (
    AbstractReadRepositories,
    AbstractWriteRepositories,
)
from data_reaper.infrastructure.db.read_repositories import (
    MongoReadRepositories,
)
from data_reaper.infrastructure.db.write_repositories import (
    MongoWriteRepositories,
)
from data_reaper.main import app
from data_reaper.presentation.api.dependencies import (
    get_current_user,
    get_dataset_file_storage,
    get_import_dispatcher,
    get_read_repositories,
    get_token_verifier,
    get_user_directory,
    get_write_repositories,
)
from data_reaper.schemas.auth import UserOut
from pymongo import AsyncMongoClient

ADMIN = UserOut(
    id="admin-1",
    email="admin@example.com",
    role="admin",
    created_at=datetime(2026, 1, 1),
)
MEMBER = UserOut(
    id="member-1",
    email="member@example.com",
    role="user",
    created_at=datetime(2026, 1, 1),
)
USERS = {"admin": ADMIN, "member": MEMBER}


@asynccontextmanager
async def _serve_app(
    mongo_client: AsyncMongoClient, database_name: str
) -> AsyncGenerator[httpx.AsyncClient, None]:
    """
    An HTTP client on the real app whose repository sets point at
    `database_name` through `mongo_client`; overrides are restored
    afterwards (R3.5.3).
    """

    async def _get_read_repositories() -> AbstractReadRepositories:
        return MongoReadRepositories(mongo_client, database_name, REPOSITORY_FACTORIES)

    async def _get_write_repositories() -> AsyncGenerator[
        AbstractWriteRepositories, None
    ]:
        async with MongoWriteRepositories(
            mongo_client, database_name, REPOSITORY_FACTORIES
        ) as write_repositories:
            yield write_repositories

    previous_overrides = dict(app.dependency_overrides)
    app.dependency_overrides[get_read_repositories] = _get_read_repositories
    app.dependency_overrides[get_write_repositories] = _get_write_repositories
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as http_client:
            yield http_client
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous_overrides)


@pytest.fixture
def serve_app():
    """Open an app client on a Mongo client of the test's choosing."""
    return _serve_app


@pytest.fixture
async def client(
    mongo_database, import_dispatcher, file_storage, token_verifier, user_directory
) -> AsyncGenerator[httpx.AsyncClient, None]:
    async with _serve_app(*mongo_database) as http_client:
        app.dependency_overrides[get_import_dispatcher] = lambda: import_dispatcher
        app.dependency_overrides[get_dataset_file_storage] = lambda: file_storage
        app.dependency_overrides[get_token_verifier] = lambda: token_verifier
        app.dependency_overrides[get_user_directory] = lambda: user_directory
        yield http_client


@pytest.fixture
def act_as():
    """Authenticate every following request as `admin` or `member`."""

    def _act_as(role: str) -> UserOut:
        user = USERS[role]
        app.dependency_overrides[get_current_user] = lambda: user
        return user

    return _act_as


@pytest.fixture
def insert_record(mongo_database):
    """Store a dataset record document straight in the test database."""

    async def _insert(collection: str, **fields) -> None:
        client, database_name = mongo_database
        now = datetime(2026, 10, 5, 10)
        await client[database_name][collection].insert_one(
            {
                "source": "thefork.es",
                "source_url": "https://www.thefork.es/r/1",
                "categories": [],
                "content_hash": "hash",
                "created_at": now,
                "updated_at": now,
                "last_seen_at": now,
                "crawler_id": None,
                "last_execution_id": None,
                "last_import_id": None,
                **fields,
            }
        )

    return _insert
