"""Centralized settings for the PlantPal backend.

Uses pydantic-settings so values can be overridden via environment
variables or a ``.env`` file.  Keep defaults production-safe enough for
local use but obviously not real secrets.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- Core / CORS -------------------------------------------------
    cors_origins: str = "http://localhost:8501,http://localhost:5173"

    # --- Redis / rate limit -----------------------------------------
    redis_url: str = "redis://localhost:6379/0"
    rate_limit_per_minute: int = 60
    cache_ttl_seconds: int = 60
    cache_enabled: bool = True

    # --- JWT / security ---------------------------------------------
    jwt_secret: str = "change-me-in-production-please-32-bytes-min"
    jwt_issuer: str = "plantpal-backend"
    jwt_audience: str = "plantpal-clients"
    jwt_expiry_minutes: int = 30
    jwt_algorithm: str = "HS256"

    # --- Default seeded user (dev/demo only) ------------------------
    default_editor_username: str = "gardener"
    default_editor_password: str = "plantpal"

    # --- AI advisor service -----------------------------------------
    ai_service_url: str = "http://localhost:8001"
    ai_service_timeout: float = 15.0

    # --- Async refresher --------------------------------------------
    api_base_url: str = "http://localhost:8000"
    refresh_max_concurrency: int = 4
    trace_id: str = "plantpal-refresh"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
