import pytest
from data_reaper.core.config import Settings
from pydantic import ValidationError


def test_imports_upsert_500_rows_per_transaction_by_default():
    assert 500 == Settings(_env_file=None).import_batch_size


@pytest.mark.parametrize("batch_size", [0, -1, 5001])
def test_the_batch_size_stays_within_a_transactions_limits(batch_size):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, import_batch_size=batch_size)


def test_csvs_are_read_from_the_mounted_folder_by_default():
    assert "/var/lib/data_reaper/csv" == (Settings(_env_file=None).dataset_import_dir)


def test_tokens_are_verified_against_night_crawlers_keycloak_by_default():
    settings = Settings(_env_file=None)

    assert (
        "http://localhost:8180/realms/night-crawler",
        "http://keycloak:8080/realms/night-crawler/protocol/openid-connect/certs",
        "importer-api",
    ) == (settings.oidc_issuer, settings.oidc_jwks_url, settings.oidc_audience)


def test_accounts_are_managed_as_the_importer_api_service_account_by_default():
    settings = Settings(_env_file=None)

    assert ("http://keycloak:8080", "night-crawler", "importer-api") == (
        settings.keycloak_url,
        settings.keycloak_realm,
        settings.keycloak_admin_client_id,
    )
    assert "" == settings.keycloak_admin_client_secret.get_secret_value()


@pytest.mark.parametrize("setting", ["jwt_secret", "jwt_algorithm", "redis_url"])
def test_local_auth_settings_are_gone(setting):
    assert setting not in Settings.model_fields
