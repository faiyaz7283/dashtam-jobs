"""Unit tests for session-related background tasks.

Tests the check_expiring_sessions task logic with mocked dependencies.

Reference:
    - docs/architecture/sse-architecture.md Section 3.6
    - GitHub Issue #258
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from dashtam_jobs.events.session import SessionExpiringSoon
from dashtam_jobs.infrastructure.repositories.session import ExpiringSession
from dashtam_jobs.tasks.sessions import check_expiring_sessions


@pytest.mark.unit
async def test_check_expiring_sessions_returns_counts(
    mock_context: MagicMock,
    mock_session_repository: MagicMock,
) -> None:
    """Test that check_expiring_sessions returns correct counts."""
    with patch(
        "dashtam_jobs.tasks.sessions.SessionRepository",
        return_value=mock_session_repository,
    ):
        result = await check_expiring_sessions(mock_context)

    assert result["checked"] == 10  # count_active returns 10
    assert result["expiring"] == 2  # sample has 2 sessions
    assert result["notified"] == 2  # should notify for each


@pytest.mark.unit
async def test_check_expiring_sessions_with_no_expiring(
    mock_context: MagicMock,
) -> None:
    """Test when no sessions are expiring."""
    mock_repo = MagicMock()
    mock_repo.find_expiring_soon = AsyncMock(return_value=[])
    mock_repo.count_active = AsyncMock(return_value=5)

    with patch(
        "dashtam_jobs.tasks.sessions.SessionRepository",
        return_value=mock_repo,
    ):
        result = await check_expiring_sessions(mock_context)

    assert result["checked"] == 5
    assert result["expiring"] == 0
    assert result["notified"] == 0


@pytest.mark.unit
async def test_check_expiring_sessions_uses_threshold_from_settings(
    mock_context: MagicMock,
    mock_session_repository: MagicMock,
) -> None:
    """Test that threshold_minutes comes from settings."""
    with patch(
        "dashtam_jobs.tasks.sessions.SessionRepository",
        return_value=mock_session_repository,
    ):
        await check_expiring_sessions(mock_context)

    # Verify find_expiring_soon was called with minutes from settings (15)
    mock_session_repository.find_expiring_soon.assert_called_once_with(minutes=15)


@pytest.mark.unit
async def test_check_expiring_sessions_creates_events_for_each_session(
    mock_context: MagicMock,
    mock_sse_publisher: MagicMock,
    sample_expiring_sessions: list[ExpiringSession],
) -> None:
    """Test that events are created for each expiring session."""
    mock_repo = MagicMock()
    mock_repo.find_expiring_soon = AsyncMock(return_value=sample_expiring_sessions)
    mock_repo.count_active = AsyncMock(return_value=10)

    # Ensure sse_publisher is on the context
    mock_context.state.sse_publisher = mock_sse_publisher

    created_events: list[SessionExpiringSoon] = []

    # Patch SessionExpiringSoon to capture instances
    original_class = SessionExpiringSoon

    def capture_event(**kwargs: object) -> SessionExpiringSoon:
        event = original_class(**kwargs)  # type: ignore[arg-type]
        created_events.append(event)
        return event

    with (
        patch(
            "dashtam_jobs.tasks.sessions.SessionRepository",
            return_value=mock_repo,
        ),
        patch(
            "dashtam_jobs.tasks.sessions.SessionExpiringSoon",
            side_effect=capture_event,
        ),
    ):
        await check_expiring_sessions(mock_context)

    # Verify events were created for each session
    assert len(created_events) == len(sample_expiring_sessions)

    # Verify event data matches sessions
    for event, sess in zip(created_events, sample_expiring_sessions, strict=True):
        assert event.session_id == sess.id
        assert event.user_id == sess.user_id
        assert event.expires_at == sess.expires_at


@pytest.mark.unit
async def test_check_expiring_sessions_publishes_sse_events(
    mock_context: MagicMock,
    mock_sse_publisher: MagicMock,
    sample_expiring_sessions: list[ExpiringSession],
) -> None:
    """Test that SSE events are published for each expiring session."""
    mock_repo = MagicMock()
    mock_repo.find_expiring_soon = AsyncMock(return_value=sample_expiring_sessions)
    mock_repo.count_active = AsyncMock(return_value=10)

    # Ensure sse_publisher is on the context
    mock_context.state.sse_publisher = mock_sse_publisher

    with patch(
        "dashtam_jobs.tasks.sessions.SessionRepository",
        return_value=mock_repo,
    ):
        await check_expiring_sessions(mock_context)

    # Verify publish_to_user was called for each session
    assert mock_sse_publisher.publish_to_user.call_count == len(
        sample_expiring_sessions
    )

    # Verify the correct event type was used
    for call in mock_sse_publisher.publish_to_user.call_args_list:
        kwargs = call.kwargs
        assert kwargs["event_type"] == "security.session.expiring"
        assert "session_id" in kwargs["data"]
        assert "expires_in_seconds" in kwargs["data"]


@pytest.mark.unit
async def test_check_expiring_sessions_logs_each_expiring_session(
    mock_context: MagicMock,
    mock_sse_publisher: MagicMock,
    sample_expiring_sessions: list[ExpiringSession],
) -> None:
    """Test that each expiring session is logged."""
    mock_repo = MagicMock()
    mock_repo.find_expiring_soon = AsyncMock(return_value=sample_expiring_sessions)
    mock_repo.count_active = AsyncMock(return_value=10)

    # Ensure sse_publisher is on the context
    mock_context.state.sse_publisher = mock_sse_publisher

    with (
        patch(
            "dashtam_jobs.tasks.sessions.SessionRepository",
            return_value=mock_repo,
        ),
        patch("dashtam_jobs.tasks.sessions.logger") as mock_logger,
    ):
        await check_expiring_sessions(mock_context)

    # Count "session_expiring_soon" log calls
    session_expiring_calls = [
        call
        for call in mock_logger.info.call_args_list
        if call.args and call.args[0] == "session_expiring_soon"
    ]

    assert len(session_expiring_calls) == len(sample_expiring_sessions)


@pytest.mark.unit
async def test_check_expiring_sessions_handles_empty_database(
    mock_context: MagicMock,
) -> None:
    """Test handling when database has no active sessions."""
    mock_repo = MagicMock()
    mock_repo.find_expiring_soon = AsyncMock(return_value=[])
    mock_repo.count_active = AsyncMock(return_value=0)

    with patch(
        "dashtam_jobs.tasks.sessions.SessionRepository",
        return_value=mock_repo,
    ):
        result = await check_expiring_sessions(mock_context)

    assert result["checked"] == 0
    assert result["expiring"] == 0
    assert result["notified"] == 0


@pytest.mark.unit
async def test_check_expiring_sessions_calculates_expires_in_seconds(
    mock_context: MagicMock,
    mock_sse_publisher: MagicMock,
) -> None:
    """Test that expires_in_seconds is calculated correctly."""
    from datetime import UTC, datetime, timedelta

    # Create a session expiring in exactly 5 minutes
    expiring_session = ExpiringSession(
        id=MagicMock(),
        user_id=MagicMock(),
        expires_at=datetime.now(UTC) + timedelta(minutes=5),
    )

    mock_repo = MagicMock()
    mock_repo.find_expiring_soon = AsyncMock(return_value=[expiring_session])
    mock_repo.count_active = AsyncMock(return_value=1)

    mock_context.state.sse_publisher = mock_sse_publisher

    with patch(
        "dashtam_jobs.tasks.sessions.SessionRepository",
        return_value=mock_repo,
    ):
        await check_expiring_sessions(mock_context)

    # Verify expires_in_seconds is approximately 300 (5 minutes)
    call_kwargs = mock_sse_publisher.publish_to_user.call_args.kwargs
    expires_in = call_kwargs["data"]["expires_in_seconds"]

    # Allow 5 second tolerance for test execution time
    assert 295 <= expires_in <= 305


@pytest.mark.unit
async def test_check_expiring_sessions_handles_negative_expiry(
    mock_context: MagicMock,
    mock_sse_publisher: MagicMock,
) -> None:
    """Test that negative expires_in_seconds is clamped to 0."""
    from datetime import UTC, datetime, timedelta

    # Create a session that has already expired (edge case)
    expired_session = ExpiringSession(
        id=MagicMock(),
        user_id=MagicMock(),
        expires_at=datetime.now(UTC) - timedelta(minutes=1),
    )

    mock_repo = MagicMock()
    mock_repo.find_expiring_soon = AsyncMock(return_value=[expired_session])
    mock_repo.count_active = AsyncMock(return_value=1)

    mock_context.state.sse_publisher = mock_sse_publisher

    with patch(
        "dashtam_jobs.tasks.sessions.SessionRepository",
        return_value=mock_repo,
    ):
        await check_expiring_sessions(mock_context)

    # Verify expires_in_seconds is clamped to 0
    call_kwargs = mock_sse_publisher.publish_to_user.call_args.kwargs
    expires_in = call_kwargs["data"]["expires_in_seconds"]

    assert expires_in == 0
