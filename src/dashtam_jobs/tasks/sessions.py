"""Session-related background tasks.

Tasks for checking and managing user sessions.

Reference:
    - docs/architecture/sse-architecture.md Section 3.6
    - GitHub Issue #258: Security and Session Notifications via SSE
"""

from typing import Annotated, Any

from taskiq import Context, TaskiqDepends

from dashtam_jobs.broker import broker
from dashtam_jobs.core.logging import get_logger
from dashtam_jobs.core.settings import get_settings
from dashtam_jobs.events.session import SessionExpiringSoon
from dashtam_jobs.infrastructure.repositories.session import SessionRepository

logger = get_logger(__name__)
_settings = get_settings()


@broker.task(
    retry_on_error=True,
    max_retries=3,
    timeout=300,
    labels={"category": "security", "schedule": "*/5 * * * *"},
)
async def check_expiring_sessions(
    context: Annotated[Context, TaskiqDepends()],
) -> dict[str, Any]:
    """Check for user sessions expiring within threshold.

    Runs every 5 minutes via scheduler. Finds active sessions expiring
    within the configured threshold and emits security.session.expiring
    SSE events for each.

    Args:
        context: TaskIQ context with injected dependencies.
            - context.state.database: Database instance for sessions.
            - context.state.sse_publisher: SSE publisher for notifications.

    Returns:
        Dict with counts: {"checked": N, "expiring": M, "notified": K}

    Example:
        # Enqueue manually (for testing)
        await check_expiring_sessions.kiq()

        # Scheduled via cron (production)
        # See scheduler.py for cron configuration
    """
    threshold_minutes = _settings.session_expiry_threshold_minutes

    logger.info(
        "check_expiring_sessions_started",
        threshold_minutes=threshold_minutes,
    )

    async with context.state.database.get_session() as session:
        repo = SessionRepository(session)

        # Query for expiring sessions
        expiring = await repo.find_expiring_soon(minutes=threshold_minutes)
        total_active = await repo.count_active()

        # Publish SSE events for each expiring session
        # Events are delivered to clients via Redis pub/sub
        sse_publisher = context.state.sse_publisher
        notified = 0

        for sess in expiring:
            event = SessionExpiringSoon(
                session_id=sess.id,
                user_id=sess.user_id,
                expires_at=sess.expires_at,
            )

            # Calculate seconds until expiration
            from datetime import UTC, datetime

            now = datetime.now(UTC)
            expires_in_seconds = int((event.expires_at - now).total_seconds())

            # Publish SSE event to user's channel
            await sse_publisher.publish_to_user(
                user_id=event.user_id,
                event_type="security.session.expiring",
                data={
                    "session_id": str(event.session_id),
                    "expires_in_seconds": max(0, expires_in_seconds),
                },
            )

            logger.info(
                "session_expiring_soon",
                session_id=str(event.session_id),
                user_id=str(event.user_id),
                expires_in_seconds=expires_in_seconds,
            )
            notified += 1

    result = {
        "checked": total_active,
        "expiring": len(expiring),
        "notified": notified,
    }

    logger.info(
        "check_expiring_sessions_completed",
        **result,
    )

    return result
