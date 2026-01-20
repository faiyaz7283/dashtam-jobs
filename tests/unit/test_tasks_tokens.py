"""Unit tests for token-related background tasks.

Tests the check_expiring_tokens task logic with mocked dependencies.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from dashtam_jobs.events.provider import ProviderTokenExpiringSoon
from dashtam_jobs.infrastructure.repositories.provider_connection import (
    ExpiringConnection,
)
from dashtam_jobs.tasks.tokens import check_expiring_tokens


@pytest.mark.unit
async def test_check_expiring_tokens_returns_counts(
    mock_context: MagicMock,
    mock_repository: MagicMock,
) -> None:
    """Test that check_expiring_tokens returns correct counts."""
    with patch(
        "dashtam_jobs.tasks.tokens.ProviderConnectionRepository",
        return_value=mock_repository,
    ):
        result = await check_expiring_tokens(mock_context)

    assert result["checked"] == 10  # count_active returns 10
    assert result["expiring"] == 2  # sample has 2 connections
    assert result["notified"] == 2  # should notify for each


@pytest.mark.unit
async def test_check_expiring_tokens_with_no_expiring(
    mock_context: MagicMock,
) -> None:
    """Test when no tokens are expiring."""
    mock_repo = MagicMock()
    mock_repo.find_expiring_soon = AsyncMock(return_value=[])
    mock_repo.count_active = AsyncMock(return_value=5)

    with patch(
        "dashtam_jobs.tasks.tokens.ProviderConnectionRepository",
        return_value=mock_repo,
    ):
        result = await check_expiring_tokens(mock_context)

    assert result["checked"] == 5
    assert result["expiring"] == 0
    assert result["notified"] == 0


@pytest.mark.unit
async def test_check_expiring_tokens_uses_threshold_from_settings(
    mock_context: MagicMock,
    mock_repository: MagicMock,
) -> None:
    """Test that threshold_hours comes from settings."""
    with patch(
        "dashtam_jobs.tasks.tokens.ProviderConnectionRepository",
        return_value=mock_repository,
    ):
        await check_expiring_tokens(mock_context)

    # Verify find_expiring_soon was called with hours from settings (24)
    mock_repository.find_expiring_soon.assert_called_once_with(hours=24)


@pytest.mark.unit
async def test_check_expiring_tokens_creates_events_for_each_connection(
    mock_context: MagicMock,
    mock_sse_publisher: MagicMock,
    sample_expiring_connections: list[ExpiringConnection],
) -> None:
    """Test that events are created for each expiring connection."""
    mock_repo = MagicMock()
    mock_repo.find_expiring_soon = AsyncMock(return_value=sample_expiring_connections)
    mock_repo.count_active = AsyncMock(return_value=10)

    # Ensure sse_publisher is on the context
    mock_context.state.sse_publisher = mock_sse_publisher

    created_events: list[ProviderTokenExpiringSoon] = []

    # Patch ProviderTokenExpiringSoon to capture instances
    original_class = ProviderTokenExpiringSoon

    def capture_event(**kwargs: object) -> ProviderTokenExpiringSoon:
        event = original_class(**kwargs)  # type: ignore[arg-type]
        created_events.append(event)
        return event

    with (
        patch(
            "dashtam_jobs.tasks.tokens.ProviderConnectionRepository",
            return_value=mock_repo,
        ),
        patch(
            "dashtam_jobs.tasks.tokens.ProviderTokenExpiringSoon",
            side_effect=capture_event,
        ),
    ):
        await check_expiring_tokens(mock_context)

    # Verify events were created for each connection
    assert len(created_events) == len(sample_expiring_connections)

    # Verify event data matches connections
    for event, conn in zip(created_events, sample_expiring_connections, strict=True):
        assert event.connection_id == conn.id
        assert event.user_id == conn.user_id
        assert event.provider_slug == conn.provider_slug
        assert event.expires_at == conn.credentials_expires_at


@pytest.mark.unit
async def test_check_expiring_tokens_logs_each_expiring_connection(
    mock_context: MagicMock,
    mock_sse_publisher: MagicMock,
    sample_expiring_connections: list[ExpiringConnection],
) -> None:
    """Test that each expiring connection is logged."""
    mock_repo = MagicMock()
    mock_repo.find_expiring_soon = AsyncMock(return_value=sample_expiring_connections)
    mock_repo.count_active = AsyncMock(return_value=10)

    # Ensure sse_publisher is on the context
    mock_context.state.sse_publisher = mock_sse_publisher

    with (
        patch(
            "dashtam_jobs.tasks.tokens.ProviderConnectionRepository",
            return_value=mock_repo,
        ),
        patch("dashtam_jobs.tasks.tokens.logger") as mock_logger,
    ):
        await check_expiring_tokens(mock_context)

    # Count "token_expiring_soon" log calls
    token_expiring_calls = [
        call
        for call in mock_logger.info.call_args_list
        if call.args and call.args[0] == "token_expiring_soon"
    ]

    assert len(token_expiring_calls) == len(sample_expiring_connections)


@pytest.mark.unit
async def test_check_expiring_tokens_handles_empty_database(
    mock_context: MagicMock,
) -> None:
    """Test handling when database has no active connections."""
    mock_repo = MagicMock()
    mock_repo.find_expiring_soon = AsyncMock(return_value=[])
    mock_repo.count_active = AsyncMock(return_value=0)

    with patch(
        "dashtam_jobs.tasks.tokens.ProviderConnectionRepository",
        return_value=mock_repo,
    ):
        result = await check_expiring_tokens(mock_context)

    assert result["checked"] == 0
    assert result["expiring"] == 0
    assert result["notified"] == 0
