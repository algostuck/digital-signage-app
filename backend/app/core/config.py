from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    app_name: str = "Digital Signage Cloud"
    environment: str = "development"  # development | test | staging | production
    debug: bool = False
    api_v1_prefix: str = "/api/v1"

    database_url: str = "postgresql+asyncpg://signage:signage@localhost:5432/signage"
    redis_url: str = "redis://localhost:6379/0"

    jwt_secret: str = "change-me"  # noqa: S105 - dev default; production boot fails on it below
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 14

    # Storage (ADR-004): "s3" for any S3-compatible endpoint (MinIO in dev
    # compose), "local" for disk-backed development without object storage.
    storage_backend: str = "local"
    local_storage_dir: str = "./var/storage"
    s3_endpoint: str = "http://localhost:9000"
    s3_bucket: str = "signage-media"
    s3_access_key: str = ""
    s3_secret_key: str = ""
    s3_region: str = "us-east-1"
    cdn_url: str = ""
    signed_url_ttl_seconds: int = 900
    upload_url_ttl_seconds: int = 3600

    # Upload policy (FR-MED-001 / FR-SET-001)
    max_upload_size_mb: int = 512
    allowed_mime_prefixes: list[str] = [
        "image/",
        "video/",
        "audio/",
        "application/pdf",
        "text/html",
        "text/plain",
        "application/json",
        "application/zip",  # player update packages (P2-DEV-004)
    ]

    # Run media processing in-request (dev/test) instead of via Celery worker.
    media_processing_inline: bool = True
    # Run deployment fan-out in-request (dev/test) instead of via Celery worker.
    publishing_inline: bool = True

    # Device health (FR-SET-002 / FR-MON-006)
    device_heartbeat_interval_seconds: int = 60
    device_offline_after_seconds: int = 300
    device_warning_after_seconds: int = 150

    # Rate limiting (SRS §16), per minute
    rate_limit_enabled: bool = True
    rate_limit_login_per_minute: int = 10
    # Generous: a whole store fleet may re-bootstrap behind one NAT IP.
    rate_limit_register_per_minute: int = 120
    rate_limit_uploads_per_minute: int = 120
    rate_limit_heartbeat_per_minute: int = 60
    rate_limit_events_per_minute: int = 120

    cors_origins: list[str] = ["http://localhost:5173"]

    default_page_size: int = 50
    max_page_size: int = 200

    log_level: str = "INFO"
    log_json: bool = True

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    # Fail fast rather than run production with a guessable signing key.
    if settings.is_production and (
        settings.jwt_secret == "change-me" or len(settings.jwt_secret) < 32  # noqa: S105
    ):
        raise RuntimeError(
            "JWT_SECRET must be set to a random value of at least 32 characters in production"
        )
    return settings
