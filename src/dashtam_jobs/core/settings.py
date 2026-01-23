"""Application settings loaded from environment.

All values come from environment variables.
No hardcoded defaults for environment-specific values.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment.

    All values come from environment variables.
    No hardcoded defaults for environment-specific values.

    Attributes:
        redis_url: Redis connection URL for task queue and results.
        database_url: PostgreSQL connection URL for database access.
        job_result_ttl: Time-to-live for job results in seconds.
        worker_concurrency: Maximum concurrent async tasks per worker.
        log_level: Logging verbosity level.
        token_expiry_threshold_hours: Hours before token expiry to trigger alerts.
        token_check_cron: Cron expression for token expiry check schedule.
    """

    # Required - no defaults (must be set in env)
    redis_url: str
    database_url: str

    # Optional with sensible defaults
    job_result_ttl: int = 86400  # 24 hours
    worker_concurrency: int = 10
    log_level: str = "INFO"

    # Token expiry check configuration
    token_expiry_threshold_hours: int = 24
    token_check_cron: str = "*/15 * * * *"

    # Session expiry check configuration
    session_expiry_threshold_minutes: int = 15
    session_check_cron: str = "*/5 * * * *"

    model_config = SettingsConfigDict(
        env_file="env/.env.dev",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance.

    Uses lru_cache to ensure settings are only loaded once.
    This pattern allows for lazy initialization and easier testing.

    Returns:
        Settings instance loaded from environment.
    """
    return Settings()  # type: ignore[call-arg]


# Convenience property for direct access (lazy-loaded)
class _SettingsProxy:
    """Proxy that lazily loads settings on first access."""

    def __getattr__(self, name: str) -> object:
        """Delegate attribute access to the actual settings instance."""
        return getattr(get_settings(), name)


settings = _SettingsProxy()
