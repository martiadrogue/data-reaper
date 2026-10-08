from datetime import UTC, datetime, timedelta

import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from data_reaper.domain.exceptions import (
    ExternalServiceException,
    ValidationException,
)
from data_reaper.domain.ports.token_verifier import AuthenticatedUser


@pytest.mark.anyio
async def test_a_valid_token_resolves_to_its_user(token_verifier, issue_token):
    token = issue_token(roles=["offline_access", "viewer", "admin"])

    user = await token_verifier.verify(token)

    assert AuthenticatedUser("kc-user-1", "dora@example.com", "admin") == user


@pytest.mark.anyio
@pytest.mark.parametrize(
    "token_claims",
    [
        {"exp": datetime.now(UTC) - timedelta(minutes=1)},
        {"iss": "http://elsewhere.test/realms/night-crawler"},
        {"aud": ["night-crawler-api"]},
        {"roles": ["offline_access"]},
        {"email": None},
        {"sub": None},
    ],
    ids=["expired", "wrong-issuer", "wrong-audience", "no-role", "no-email", "no-sub"],
)
async def test_an_unacceptable_token_is_a_401(
    token_verifier, issue_token, token_claims
):
    with pytest.raises(ValidationException) as exc_info:
        await token_verifier.verify(issue_token(**token_claims))

    assert 401 == exc_info.value.status_code
    assert "Invalid or expired session token" == exc_info.value.message


@pytest.mark.anyio
async def test_a_token_signed_by_another_key_is_a_401(token_verifier, issue_token):
    stranger_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    with pytest.raises(ValidationException) as exc_info:
        await token_verifier.verify(issue_token(key=stranger_key))

    assert 401 == exc_info.value.status_code


@pytest.mark.anyio
async def test_a_malformed_token_is_a_401(token_verifier):
    with pytest.raises(ValidationException) as exc_info:
        await token_verifier.verify("not-a-jwt")

    assert 401 == exc_info.value.status_code


@pytest.mark.anyio
async def test_an_unreachable_jwks_is_a_502(create_token_verifier, issue_token):
    verifier = create_token_verifier("http://127.0.0.1:9/certs")

    with pytest.raises(ExternalServiceException) as exc_info:
        await verifier.verify(issue_token())

    assert 502 == exc_info.value.status_code
