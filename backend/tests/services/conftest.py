"""Service tests share repository and port fakes."""

import pytest
from data_reaper.domain.exceptions import ValidationException
from data_reaper.domain.ports.token_verifier import (
    AbstractTokenVerifier,
    AuthenticatedUser,
)


class FakeTokenVerifier(AbstractTokenVerifier):
    """Accept only the tokens a test registered in `users`."""

    def __init__(self) -> None:
        self.users: dict[str, AuthenticatedUser] = {}

    async def verify(self, token: str) -> AuthenticatedUser:
        if token not in self.users:
            raise ValidationException("Invalid or expired session token", 401)
        return self.users[token]


@pytest.fixture
def token_verifier_fake() -> FakeTokenVerifier:
    return FakeTokenVerifier()
