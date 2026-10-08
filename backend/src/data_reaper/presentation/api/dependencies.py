"""Dependencies routes declare; the stubs are bound in `core/di.py`.

Routes only see the abstractions, never a concrete database client.
"""

from collections.abc import AsyncGenerator

from data_reaper.domain.exceptions import ValidationException
from data_reaper.domain.ports.dataset_file_storage import (
    AbstractDatasetFileStorage,
)
from data_reaper.domain.ports.import_dispatcher import (
    AbstractImportDispatcher,
)
from data_reaper.domain.ports.repository_sets import (
    AbstractReadRepositories,
    AbstractWriteRepositories,
)
from data_reaper.domain.ports.token_verifier import AbstractTokenVerifier
from data_reaper.domain.ports.user_directory import AbstractUserDirectory
from data_reaper.schemas.auth import UserOut
from data_reaper.services.auth_service import get_user_from_token
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

bearer_scheme = HTTPBearer(auto_error=False)


async def get_token_verifier() -> AbstractTokenVerifier:
    """Stub for the access token verifier; bound in `core/di.py`.

    Raises:
        NotImplementedError: the dependency was never overridden.
    """
    raise NotImplementedError("Dependency not wired up at startup.")


async def get_user_directory() -> AbstractUserDirectory:
    """Stub for the identity provider's accounts; bound in `core/di.py`.

    Raises:
        NotImplementedError: the dependency was never overridden.
    """
    raise NotImplementedError("Dependency not wired up at startup.")


async def get_read_repositories() -> AbstractReadRepositories:
    """Stub for read repositories; `core/di.py` overrides it.

    Fails loudly if left unbound rather than silently reaching a real
    database.

    Raises:
        NotImplementedError: the dependency was never overridden.
    """
    raise NotImplementedError("Dependency not wired up at startup.")


async def get_write_repositories() -> AsyncGenerator[AbstractWriteRepositories, None]:
    """Stub for write repositories; `core/di.py` overrides it.

    Raises:
        NotImplementedError: the dependency was never overridden.
    """
    raise NotImplementedError("Dependency not wired up at startup.")


async def get_import_dispatcher() -> AbstractImportDispatcher:
    """Stub for the import queue dispatcher; bound in `core/di.py`.

    Raises:
        NotImplementedError: the dependency was never overridden.
    """
    raise NotImplementedError("Dependency not wired up at startup.")


async def get_dataset_file_storage() -> AbstractDatasetFileStorage:
    """Stub for the validated CSV folder; bound in `core/di.py`.

    Raises:
        NotImplementedError: the dependency was never overridden.
    """
    raise NotImplementedError("Dependency not wired up at startup.")


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    token_verifier: AbstractTokenVerifier = Depends(get_token_verifier),
) -> UserOut:
    """Return the authenticated user from the Keycloak bearer token.

    The token says who the user is and their role, so no database is
    read and a write request's transaction starts only after the user
    is known. Routes that don't declare this dependency stay public;
    there is no allow-list to maintain. A missing token is a 401 like
    a bad one, through the single `AppException` handler.

    Raises:
        ValidationException: the token is missing, invalid, or expired,
            or carries no email or known role (401).
        ExternalServiceException: Keycloak's signing keys can't be
            fetched (502).
    """
    if None is credentials:
        raise ValidationException("Not authenticated", 401)
    return await get_user_from_token(token_verifier, credentials.credentials)


async def require_admin(
    current_user: UserOut = Depends(get_current_user),
) -> UserOut:
    """Return the current user if they are an admin.

    Runs after authentication, so an anonymous request still gets 401,
    not 403.

    Raises:
        ValidationException: the user is not an admin (403).
    """
    if "admin" != current_user.role:
        raise ValidationException("This action requires an admin role.", 403)
    return current_user
