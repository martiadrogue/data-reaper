"""The Composition Root.

The only module that imports concrete `infrastructure/` adapters and
binds them to the domain ports (CONTRIBUTING R1.1.3, R1.2.9), so
swapping a backend means editing only this file. It also owns the
MongoDB client's lifecycle, so `main.py` never imports
`infrastructure/` itself.
"""

import logging
from collections.abc import AsyncGenerator, AsyncIterator
from contextlib import asynccontextmanager
from functools import lru_cache

from data_reaper.celery import app as celery_app
from data_reaper.core.config import get_settings
from data_reaper.core.telemetry import get_meter
from data_reaper.domain.bundles.import_infrastructure import (
    ImportInfrastructure,
)
from data_reaper.domain.bundles.repository_factories import (
    RepositorySetFactories,
)
from data_reaper.domain.ports.dataset_file_storage import (
    AbstractDatasetFileStorage,
)
from data_reaper.domain.ports.import_dispatcher import (
    AbstractImportDispatcher,
)
from data_reaper.domain.ports.import_metrics import AbstractImportMetrics
from data_reaper.domain.ports.repository_sets import (
    AbstractReadRepositories,
    AbstractWriteRepositories,
)
from data_reaper.domain.ports.token_verifier import AbstractTokenVerifier
from data_reaper.domain.ports.user_directory import AbstractUserDirectory
from data_reaper.infrastructure.db.dataset_event_repository import (
    MongoDatasetEventRepository,
)
from data_reaper.infrastructure.db.dataset_import_repository import (
    MongoDatasetImportRepository,
)
from data_reaper.infrastructure.db.dataset_place_repository import (
    MongoDatasetPlaceRepository,
)
from data_reaper.infrastructure.db.read_repositories import (
    MongoReadRepositories,
)
from data_reaper.infrastructure.db.repository_factories import (
    RepositoryFactory,
)
from data_reaper.infrastructure.db.schema import initialize_database
from data_reaper.infrastructure.db.write_repositories import (
    MongoWriteRepositories,
)
from data_reaper.infrastructure.external.jwks_token_verifier import (
    JwksTokenVerifier,
)
from data_reaper.infrastructure.external.keycloak_user_directory import (
    KeycloakUserDirectory,
)
from data_reaper.infrastructure.storage.local_dataset_file_storage import (
    LocalDatasetFileStorage,
)
from data_reaper.infrastructure.tasks.celery_import_dispatcher import (
    CeleryImportDispatcher,
)
from data_reaper.infrastructure.telemetry.open_telemetry_import_metrics import (
    OpenTelemetryImportMetrics,
)
from data_reaper.presentation.api.dependencies import (
    get_dataset_file_storage,
    get_import_dispatcher,
    get_read_repositories,
    get_token_verifier,
    get_user_directory,
    get_write_repositories,
)
from fastapi import FastAPI
from pymongo import AsyncMongoClient

logger = logging.getLogger(__name__)

REPOSITORY_FACTORIES: dict[str, RepositoryFactory] = {
    "dataset_imports": MongoDatasetImportRepository,
    "dataset_places": MongoDatasetPlaceRepository,
    "dataset_events": MongoDatasetEventRepository,
}
"""Which adapter backs each repository port of both repository sets.

Write repositories build them per transaction, bound to its session;
read repositories build them without one.
"""

_settings = get_settings()


@lru_cache
def _get_client() -> AsyncMongoClient:
    """Return the web process's MongoDB client, created on first use.

    Not at import: PyMongo's tracing listener (`setup_telemetry`) only
    reaches clients created after it. The client connects lazily and
    binds to the event loop of its first operation, uvicorn's only one.
    """
    return AsyncMongoClient(_settings.mongo_url, tz_aware=False)


_import_dispatcher = CeleryImportDispatcher(celery_app)
_token_verifier = JwksTokenVerifier(
    _settings.oidc_jwks_url, _settings.oidc_issuer, _settings.oidc_audience
)


async def _get_read_repositories() -> AbstractReadRepositories:
    """Return read repositories for one request."""
    return create_read_repositories()


async def _get_write_repositories() -> AsyncGenerator[AbstractWriteRepositories, None]:
    """Yield write repositories whose transaction spans one request."""
    async with create_write_repositories() as write_repositories:
        yield write_repositories


def create_read_repositories() -> AbstractReadRepositories:
    """Return new read repositories, for callers without `Depends`."""
    return MongoReadRepositories(
        _get_client(), _settings.mongo_database, REPOSITORY_FACTORIES
    )


def create_write_repositories() -> AbstractWriteRepositories:
    """Return new write repositories, for callers without `Depends`."""
    return MongoWriteRepositories(
        _get_client(), _settings.mongo_database, REPOSITORY_FACTORIES
    )


def create_import_dispatcher() -> AbstractImportDispatcher:
    """Return the process-wide Celery import dispatcher."""
    return _import_dispatcher


async def _get_import_dispatcher() -> AbstractImportDispatcher:
    """Return the import dispatcher for one request."""
    return _import_dispatcher


def create_user_directory() -> AbstractUserDirectory:
    """Return a Keycloak directory with a connection pool of its own.

    The pool is bound to the event loop that first uses it, so the web
    process keeps one; anything else opens and closes its own.
    """
    return KeycloakUserDirectory(
        _settings.keycloak_url,
        _settings.keycloak_realm,
        _settings.keycloak_admin_client_id,
        _settings.keycloak_admin_client_secret.get_secret_value(),
    )


_user_directory = create_user_directory()


async def _get_user_directory() -> AbstractUserDirectory:
    """Return the web process's directory, sharing its admin token."""
    return _user_directory


async def _get_token_verifier() -> AbstractTokenVerifier:
    """Return the process-wide verifier, so its key cache is shared."""
    return _token_verifier


def create_dataset_file_storage() -> AbstractDatasetFileStorage:
    """Return the folder of validated CSVs to import."""
    return LocalDatasetFileStorage(_settings.dataset_import_dir)


def create_import_metrics() -> AbstractImportMetrics:
    """Return where finished imports are recorded for monitoring."""
    return OpenTelemetryImportMetrics(get_meter())


@asynccontextmanager
async def open_task_repositories() -> AsyncIterator[RepositorySetFactories]:
    """Yield repository factories on a MongoDB client of the task's own.

    Each Celery task runs in a new event loop (`asyncio.run`) and an
    async client is bound to the loop that first uses it, so the web
    process's client can't be shared; this one is closed afterwards.
    """
    client: AsyncMongoClient = AsyncMongoClient(_settings.mongo_url, tz_aware=False)
    try:
        yield RepositorySetFactories(
            open_read=lambda: MongoReadRepositories(
                client, _settings.mongo_database, REPOSITORY_FACTORIES
            ),
            open_write=lambda: MongoWriteRepositories(
                client, _settings.mongo_database, REPOSITORY_FACTORIES
            ),
        )
    finally:
        await client.close()


@asynccontextmanager
async def open_import_infrastructure() -> AsyncIterator[ImportInfrastructure]:
    """Yield what one import needs, and close it afterwards."""
    async with open_task_repositories() as repository_factories:
        yield ImportInfrastructure(
            repository_factories=repository_factories,
            file_storage=create_dataset_file_storage(),
            import_metrics=create_import_metrics(),
            batch_size=_settings.import_batch_size,
        )


def configure_dependencies(app: FastAPI) -> None:
    """Override the `presentation/api/dependencies.py` stubs."""
    app.dependency_overrides[get_import_dispatcher] = _get_import_dispatcher
    app.dependency_overrides[get_token_verifier] = _get_token_verifier
    app.dependency_overrides[get_user_directory] = _get_user_directory
    app.dependency_overrides[get_dataset_file_storage] = create_dataset_file_storage
    app.dependency_overrides[get_read_repositories] = _get_read_repositories
    app.dependency_overrides[get_write_repositories] = _get_write_repositories
    logger.info("Composition root: infrastructure dependencies wired.")


async def startup_infrastructure() -> None:
    """Prepare the database.

    No admin is seeded: Night Crawler's Keycloak realm import does.
    """
    await initialize_database(_get_client()[_settings.mongo_database])


async def shutdown_infrastructure() -> None:
    """Close the database and Keycloak connection pools."""
    await _user_directory.aclose()
    await _get_client().close()
