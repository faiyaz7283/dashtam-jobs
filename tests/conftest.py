"""Test configuration and fixtures for dashtam-jobs."""

import os
from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from taskiq import InMemoryBroker

from dashtam_jobs.infrastructure.repositories.provider_connection import (
    ExpiringConnection,
)
from dashtam_jobs.infrastructure.repositories.session import ExpiringSession


@pytest.fixture(autouse=True)
def mock_env_vars() -> Generator[None]:
    """Set up mock environment variables for testing.

    This fixture runs automatically for all tests to ensure
    settings can be loaded without real environment variables.
    """
    env_vars = {
        "REDIS_URL": "redis://localhost:6379/0",
        "DATABASE_URL": "postgresql+asyncpg://test:test@localhost:5432/test",
        "LOG_LEVEL": "DEBUG",
        "JOB_RESULT_TTL": "3600",
        "WORKER_CONCURRENCY": "5",
        "TOKEN_EXPIRY_THRESHOLD_HOURS": "24",
        "TOKEN_CHECK_CRON": "*/15 * * * *",
        "SESSION_EXPIRY_THRESHOLD_MINUTES": "15",
        "SESSION_CHECK_CRON": "*/5 * * * *",
    }
    with patch.dict(os.environ, env_vars, clear=False):
        # Clear the settings cache so new env vars are picked up
        from dashtam_jobs.core.settings import get_settings

        get_settings.cache_clear()
        yield
        get_settings.cache_clear()


@pytest.fixture
def test_broker() -> InMemoryBroker:
    """Provide an in-memory broker for unit tests.

    Returns:
        InMemoryBroker instance for testing without Redis.
    """
    return InMemoryBroker()


@pytest.fixture
def mock_database() -> MagicMock:
    """Provide a mock database instance.

    Returns:
        MagicMock configured as an async context manager for get_session().
    """
    mock_db = MagicMock()
    mock_session = AsyncMock()

    # Configure get_session as async context manager
    mock_db.get_session = MagicMock()
    mock_db.get_session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_db.get_session.return_value.__aexit__ = AsyncMock(return_value=None)

    return mock_db


@pytest.fixture
def mock_sse_publisher() -> MagicMock:
    """Provide a mock SSE publisher instance.

    Returns:
        MagicMock configured with async publish methods.
    """
    mock_publisher = MagicMock()
    mock_publisher.publish_to_user = AsyncMock(return_value=1)
    mock_publisher.broadcast = AsyncMock(return_value=1)
    return mock_publisher


@pytest.fixture
def mock_context(mock_database: MagicMock, mock_sse_publisher: MagicMock) -> MagicMock:
    """Provide a mock TaskIQ context with state.

    Args:
        mock_database: Mock database fixture.
        mock_sse_publisher: Mock SSE publisher fixture.

    Returns:
        MagicMock configured as TaskIQ Context with state.database and state.sse_publisher.
    """
    context = MagicMock()
    context.state = MagicMock()
    context.state.database = mock_database
    context.state.sse_publisher = mock_sse_publisher
    return context


@pytest.fixture
def sample_expiring_connections() -> list[ExpiringConnection]:
    """Provide sample expiring connections for testing.

    Returns:
        List of ExpiringConnection DTOs for testing.
    """
    return [
        ExpiringConnection(
            id=uuid4(),
            user_id=uuid4(),
            provider_slug="schwab",
            credentials_expires_at=datetime.now(UTC) + timedelta(hours=12),
        ),
        ExpiringConnection(
            id=uuid4(),
            user_id=uuid4(),
            provider_slug="alpaca",
            credentials_expires_at=datetime.now(UTC) + timedelta(hours=6),
        ),
    ]


@pytest.fixture
def mock_repository(
    sample_expiring_connections: list[ExpiringConnection],
) -> MagicMock:
    """Provide a mock ProviderConnectionRepository.

    Args:
        sample_expiring_connections: Sample connections to return.

    Returns:
        MagicMock configured as ProviderConnectionRepository.
    """
    repo = MagicMock()
    repo.find_expiring_soon = AsyncMock(return_value=sample_expiring_connections)
    repo.count_active = AsyncMock(return_value=10)
    return repo


def create_expiring_connection(
    provider_slug: str = "schwab",
    hours_until_expiry: int = 12,
) -> ExpiringConnection:
    """Helper to create ExpiringConnection for tests.

    Args:
        provider_slug: Provider identifier.
        hours_until_expiry: Hours until credentials expire.

    Returns:
        ExpiringConnection DTO.
    """
    return ExpiringConnection(
        id=uuid4(),
        user_id=uuid4(),
        provider_slug=provider_slug,
        credentials_expires_at=datetime.now(UTC) + timedelta(hours=hours_until_expiry),
    )


@pytest.fixture
def sample_expiring_sessions() -> list[ExpiringSession]:
    """Provide sample expiring sessions for testing.

    Returns:
        List of ExpiringSession DTOs for testing.
    """
    return [
        ExpiringSession(
            id=uuid4(),
            user_id=uuid4(),
            expires_at=datetime.now(UTC) + timedelta(minutes=10),
        ),
        ExpiringSession(
            id=uuid4(),
            user_id=uuid4(),
            expires_at=datetime.now(UTC) + timedelta(minutes=5),
        ),
    ]


@pytest.fixture
def mock_session_repository(
    sample_expiring_sessions: list[ExpiringSession],
) -> MagicMock:
    """Provide a mock SessionRepository.

    Args:
        sample_expiring_sessions: Sample sessions to return.

    Returns:
        MagicMock configured as SessionRepository.
    """
    repo = MagicMock()
    repo.find_expiring_soon = AsyncMock(return_value=sample_expiring_sessions)
    repo.count_active = AsyncMock(return_value=10)
    return repo


def create_expiring_session(
    minutes_until_expiry: int = 10,
) -> ExpiringSession:
    """Helper to create ExpiringSession for tests.

    Args:
        minutes_until_expiry: Minutes until session expires.

    Returns:
        ExpiringSession DTO.
    """
    return ExpiringSession(
        id=uuid4(),
        user_id=uuid4(),
        expires_at=datetime.now(UTC) + timedelta(minutes=minutes_until_expiry),
    )


# Re-export helpers for tests
__all__: list[Any] = ["create_expiring_connection", "create_expiring_session"]
