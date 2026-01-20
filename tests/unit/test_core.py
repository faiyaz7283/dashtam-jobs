"""Unit tests for core modules."""

import pytest


@pytest.mark.unit
def test_settings_can_be_loaded():
    """Verify settings can be loaded from environment."""
    from dashtam_jobs.core.settings import get_settings

    settings = get_settings()

    assert settings.redis_url == "redis://localhost:6379/0"
    assert settings.database_url == "postgresql+asyncpg://test:test@localhost:5432/test"
    assert settings.log_level == "DEBUG"
    assert settings.job_result_ttl == 3600
    assert settings.worker_concurrency == 5


@pytest.mark.unit
def test_settings_proxy_works():
    """Verify settings proxy provides lazy access."""
    from dashtam_jobs.core.settings import settings

    # Access via proxy should work
    assert settings.redis_url == "redis://localhost:6379/0"
    assert settings.log_level == "DEBUG"


@pytest.mark.unit
def test_logger_can_be_created():
    """Verify logger can be created."""
    from dashtam_jobs.core.logging import get_logger

    logger = get_logger("test")

    assert logger is not None


@pytest.mark.unit
def test_middleware_instantiates():
    """Verify JobLoggingMiddleware can be instantiated."""
    from dashtam_jobs.middlewares.logging import JobLoggingMiddleware

    middleware = JobLoggingMiddleware()

    assert middleware is not None
