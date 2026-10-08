"""Application settings read from the environment."""

from functools import lru_cache
from urllib.parse import quote

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-driven settings; secrets have no defaults."""

    app_name: str = Field(default="Data Reaper API")
    app_description: str = Field(default="Data Reaper API")
    app_version: str = Field(default="0.1.0")
    app_env: str = Field(default="development")
    root_path: str = Field(default="")
    cors_allow_origins: str = Field(
        default="http://localhost:3100,http://127.0.0.1:3100"
    )

    # Injected by Compose (`x-app-env`) from `MONGO_USER`,
    # `MONGO_PASSWORD`, and `MONGO_DATABASE` in `.env`.
    mongo_url: str = Field(default="mongodb://db:27017/?replicaSet=rs0")
    mongo_database: str = Field(default="data_reaper")

    # Keycloak, which Night Crawler's stack runs, issues the access
    # tokens the API accepts (RS256). Tokens always name the
    # browser-facing issuer even when a container fetched them; the
    # keys are fetched over the shared `identity` Docker network.
    oidc_issuer: str = Field(default="http://localhost:8180/realms/night-crawler")
    oidc_jwks_url: str = Field(
        default=(
            "http://keycloak:8080/realms/night-crawler/protocol/openid-connect/certs"
        )
    )
    # The `aud` a token must carry: the API's own client id.
    oidc_audience: str = Field(default="importer-api")

    # Keycloak's Admin REST API, where accounts are managed, reached as
    # the API's service account. Compose maps the secret from
    # `KC_IMPORTER_API_SECRET`; without it every user route is a 502.
    keycloak_url: str = Field(default="http://keycloak:8080")
    keycloak_realm: str = Field(default="night-crawler")
    keycloak_admin_client_id: str = Field(default="importer-api")
    keycloak_admin_client_secret: SecretStr = Field(default=SecretStr(""))

    # RabbitMQ, the Celery broker (`RABBITMQ_*` in `.env`).
    rabbitmq_user: str = Field(default="")
    rabbitmq_password: str = Field(default="")
    rabbitmq_host: str = Field(default="rabbitmq")
    # Production shares one RabbitMQ between the apps, a vhost each:
    # their queue names overlap (`dataset-import`).
    rabbitmq_vhost: str = Field(default="/")

    # The folder of validated CSVs to import, mounted read-only by
    # Compose from `CSV_SOURCE_DIR` (a crawler's `var/csv/validated`).
    dataset_import_dir: str = Field(default="/var/lib/data_reaper/csv")
    # Rows upserted per write transaction; MongoDB caps a transaction
    # at 16 MiB of oplog and 60 s by default, so keep it modest.
    import_batch_size: int = Field(default=500, gt=0, le=5000)

    # Where traces and metrics are pushed over OTLP/HTTP (Grafana
    # Alloy, `http://alloy:4318`); empty turns telemetry off. Set by
    # `make up-observability` (core/telemetry.py).
    otel_exporter_otlp_endpoint: str = Field(default="")

    @property
    def broker_url(self) -> str:
        """Return the RabbitMQ broker URL."""
        return (
            f"amqp://{self.rabbitmq_user}:{self.rabbitmq_password}"
            f"@{self.rabbitmq_host}:5672/{quote(self.rabbitmq_vhost, safe='')}"
        )

    # `extra="ignore"`: the root `.env` is shared across every compose
    # service (including the frontend's `API_BASE_URL`), so this model
    # must not reject keys it doesn't declare.
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )


@lru_cache
def get_settings() -> Settings:
    """Return the settings, read from the environment once."""
    return Settings()
