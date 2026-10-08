import asyncio
import csv
import http.server
import io
import json
import threading
import uuid
from collections.abc import AsyncGenerator, Generator
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from data_reaper.core.config import get_settings
from data_reaper.core.di import REPOSITORY_FACTORIES
from data_reaper.domain.bundles.repository_factories import (
    RepositorySetFactories,
)
from data_reaper.domain.exceptions import (
    ExternalServiceException,
    ValidationException,
)
from data_reaper.domain.model.entities import DatasetImport
from data_reaper.domain.ports.dataset_file_storage import (
    AbstractDatasetFileStorage,
    DatasetFile,
)
from data_reaper.domain.ports.import_dispatcher import (
    AbstractImportDispatcher,
)
from data_reaper.domain.ports.import_metrics import AbstractImportMetrics
from data_reaper.domain.ports.repository_sets import (
    AbstractReadRepositories,
    AbstractWriteRepositories,
)
from data_reaper.domain.ports.user_directory import (
    AbstractUserDirectory,
    DirectoryUser,
    DirectoryUserChanges,
)
from data_reaper.infrastructure.db.read_repositories import (
    MongoReadRepositories,
)
from data_reaper.infrastructure.db.schema import initialize_database
from data_reaper.infrastructure.db.write_repositories import (
    MongoWriteRepositories,
)
from data_reaper.infrastructure.external.jwks_token_verifier import (
    JwksTokenVerifier,
)
from data_reaper.schemas.auth import UserOut
from pymongo import AsyncMongoClient


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture(scope="session")
def test_database_name() -> Generator[str, None, None]:
    """
    One throwaway MongoDB database per test session, with every index
    and validator in place, dropped at the end (R3.5.4). Creating one
    per test would churn thousands of WiredTiger files.
    """
    database_name = f"data_reaper_test_{uuid.uuid4().hex[:12]}"
    asyncio.run(_run_on_database(database_name, initialize_database))
    try:
        yield database_name
    finally:
        asyncio.run(_run_on_database(database_name, _drop_database))


async def _run_on_database(database_name, action) -> None:
    # A client of its own: an async client is bound to the event loop
    # that first uses it, and each test runs on a fresh loop.
    client = AsyncMongoClient(get_settings().mongo_url)
    try:
        await action(client[database_name])
    finally:
        await client.close()


async def _drop_database(database) -> None:
    await database.client.drop_database(database.name)


@pytest.fixture
async def mongo_database(
    test_database_name,
) -> AsyncGenerator[tuple[AsyncMongoClient, str], None]:
    """A client on the test database, emptied before each test."""
    client = AsyncMongoClient(get_settings().mongo_url)
    database = client[test_database_name]
    for collection_name in await database.list_collection_names():
        await database[collection_name].delete_many({})
    try:
        yield client, test_database_name
    finally:
        await client.close()


@pytest.fixture
async def write_repositories(
    mongo_database,
) -> AsyncGenerator[AbstractWriteRepositories, None]:
    """
    Write repositories on the test database. Services commit themselves;
    teardown rolls back, since a failed write inside a transaction makes
    MongoDB abort it and a final commit would then fail.
    """
    client, database_name = mongo_database
    async with MongoWriteRepositories(
        client, database_name, REPOSITORY_FACTORIES
    ) as repositories:
        yield repositories
        await repositories.rollback()


@pytest.fixture
async def read_repositories(mongo_database) -> AbstractReadRepositories:
    """Read repositories on the test database: no transaction."""
    client, database_name = mongo_database
    return MongoReadRepositories(client, database_name, REPOSITORY_FACTORIES)


@pytest.fixture
async def repository_factories(mongo_database) -> RepositorySetFactories:
    """Open read or write repositories on the test database, like a task."""
    client, database_name = mongo_database
    return RepositorySetFactories(
        open_read=lambda: MongoReadRepositories(
            client, database_name, REPOSITORY_FACTORIES
        ),
        open_write=lambda: MongoWriteRepositories(
            client, database_name, REPOSITORY_FACTORIES
        ),
    )


class RecordingImportDispatcher(AbstractImportDispatcher):
    """Keeps every dispatch instead of enqueuing it."""

    def __init__(self) -> None:
        self.dispatched: list[str] = []

    async def dispatch(self, import_id: str) -> None:
        self.dispatched.append(import_id)


@pytest.fixture
def import_dispatcher() -> RecordingImportDispatcher:
    return RecordingImportDispatcher()


class RecordingImportMetrics(AbstractImportMetrics):
    """Keeps every finished import instead of exporting metrics."""

    def __init__(self) -> None:
        self.finished: list[DatasetImport] = []

    def record_finished(
        self, dataset_import: DatasetImport, duration_seconds: float
    ) -> None:
        self.finished.append(dataset_import)


@pytest.fixture
def import_metrics() -> RecordingImportMetrics:
    return RecordingImportMetrics()


class InMemoryFileStorage(AbstractDatasetFileStorage):
    """CSV files held as text, by name; `is_failing` breaks the folder."""

    def __init__(self) -> None:
        self.files: dict[str, str] = {}
        self.is_failing = False

    def add(self, name: str, *lines: str) -> str:
        self.files[name] = "\n".join(lines) + "\n"
        return name

    async def get_file_names(self) -> list[str]:
        if self.is_failing:
            raise ExternalServiceException("Folder unreachable.")
        return sorted(self.files)

    async def read(self, file_name: str) -> DatasetFile:
        if self.is_failing or file_name not in self.files:
            raise ExternalServiceException(f"No such file: {file_name}")
        reader = csv.DictReader(io.StringIO(self.files[file_name]))
        rows = tuple(dict(row) for row in reader)
        return DatasetFile(columns=tuple(reader.fieldnames or ()), rows=rows)


@pytest.fixture
def file_storage() -> InMemoryFileStorage:
    return InMemoryFileStorage()


@pytest.fixture
def member() -> UserOut:
    return UserOut(
        id="member-1",
        email="member@example.com",
        role="user",
        created_at=datetime(2026, 1, 1),
    )


@pytest.fixture
def admin() -> UserOut:
    return UserOut(
        id="admin-1",
        email="admin@example.com",
        role="admin",
        created_at=datetime(2026, 1, 1),
    )


TEST_ISSUER = "http://keycloak.test/realms/night-crawler"
TEST_AUDIENCE = "importer-api"
TEST_KEY_ID = "test-key"


class _JwksHandler(http.server.BaseHTTPRequestHandler):
    """Serve the test JWKS, standing in for Keycloak's certs endpoint."""

    jwks_body = b""

    def do_GET(self) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(self.jwks_body)

    def log_message(self, *args) -> None:
        pass


@pytest.fixture(scope="session")
def signing_key() -> rsa.RSAPrivateKey:
    """The RSA key test tokens are signed with; its public half is served."""
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture(scope="session")
def jwks_url(signing_key) -> Generator[str, None, None]:
    """A local HTTP server's JWKS URL publishing `signing_key`, never Keycloak."""
    jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(signing_key.public_key()))
    handler = type(
        "JwksHandler",
        (_JwksHandler,),
        {"jwks_body": json.dumps({"keys": [{**jwk, "kid": TEST_KEY_ID}]}).encode()},
    )
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/certs"
    finally:
        server.shutdown()
        server.server_close()


@pytest.fixture
def create_token_verifier(jwks_url):
    """Build a verifier for test tokens, on `jwks_url` unless given one."""

    def _create_token_verifier(url: str | None = None) -> JwksTokenVerifier:
        return JwksTokenVerifier(url or jwks_url, TEST_ISSUER, TEST_AUDIENCE)

    return _create_token_verifier


@pytest.fixture
def token_verifier(create_token_verifier) -> JwksTokenVerifier:
    return create_token_verifier()


@pytest.fixture
def issue_token(signing_key):
    """Sign a Keycloak-shaped access token; keyword arguments override claims."""

    def _issue_token(roles: list[str] | None = None, key=None, **claims: object) -> str:
        now = datetime.now(UTC)
        payload = {
            "sub": "kc-user-1",
            "email": "dora@example.com",
            "iss": TEST_ISSUER,
            "aud": [TEST_AUDIENCE, "account"],
            "iat": now,
            "exp": now + timedelta(minutes=5),
            "realm_access": {"roles": ["user"] if None is roles else roles},
        }
        payload.update(claims)
        return jwt.encode(
            payload,
            key or signing_key,
            algorithm="RS256",
            headers={"kid": TEST_KEY_ID},
        )

    return _issue_token


class FakeUserDirectory(AbstractUserDirectory):
    """Hold accounts in memory, keeping emails unique as Keycloak does."""

    def __init__(self) -> None:
        self.users: dict[str, DirectoryUser] = {}
        self.temporary_passwords: dict[str, str] = {}

    def add(
        self,
        user_id: str,
        email: str,
        role: str | None = "user",
        is_enabled: bool = True,
    ) -> DirectoryUser:
        """Store an account straight away, as if it already existed."""
        user = DirectoryUser(user_id, email, role, is_enabled, datetime(2026, 1, 1))
        self.users[user_id] = user
        return user

    async def get_all(self, limit: int, offset: int) -> list[DirectoryUser]:
        by_email = sorted(self.users.values(), key=lambda user: user.email)
        return by_email[offset : offset + limit]

    async def get_by_id(self, user_id: str) -> DirectoryUser | None:
        return self.users.get(user_id)

    async def create(
        self, email: str, role: str, temporary_password: str
    ) -> DirectoryUser:
        self._ensure_email_free(email)
        user = self.add(f"kc-{len(self.users) + 1}", email, role)
        self.temporary_passwords[user.id] = temporary_password
        return user

    async def update(
        self, user_id: str, changes: DirectoryUserChanges
    ) -> DirectoryUser:
        user = self._get_or_404(user_id)
        if changes.email and changes.email != user.email:
            self._ensure_email_free(changes.email)
        if changes.temporary_password:
            self.temporary_passwords[user_id] = changes.temporary_password
        updated = replace(
            user, email=changes.email or user.email, role=changes.role or user.role
        )
        self.users[user_id] = updated
        return updated

    async def disable(self, user_id: str) -> None:
        self.users[user_id] = replace(self._get_or_404(user_id), is_enabled=False)

    async def count_enabled_by_role(self, role: str) -> int:
        return sum(
            1 for user in self.users.values() if role == user.role and user.is_enabled
        )

    async def aclose(self) -> None:
        pass

    def _get_or_404(self, user_id: str) -> DirectoryUser:
        if user_id not in self.users:
            raise ValidationException("User not found.", 404)
        return self.users[user_id]

    def _ensure_email_free(self, email: str) -> None:
        if any(email == user.email for user in self.users.values()):
            raise ValidationException("Email already taken", 400)


@pytest.fixture
def user_directory() -> FakeUserDirectory:
    return FakeUserDirectory()
