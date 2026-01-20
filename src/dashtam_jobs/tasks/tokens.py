"""Token-related background tasks.

Tasks for checking and managing provider OAuth tokens.

Reference:
    - docs/architecture/background-jobs.md (Lines 1268-1310)
"""

from typing import Annotated, Any

from taskiq import Context, TaskiqDepends

from dashtam_jobs.broker import broker
from dashtam_jobs.core.logging import get_logger
from dashtam_jobs.core.settings import get_settings
from dashtam_jobs.events.provider import ProviderTokenExpiringSoon
from dashtam_jobs.infrastructure.repositories.provider_connection import (
    ProviderConnectionRepository,
)

logger = get_logger(__name__)
_settings = get_settings()


@broker.task(
    retry_on_error=True,
    max_retries=3,
    timeout=300,
    labels={"category": "provider", "schedule": "*/15 * * * *"},
)
async def check_expiring_tokens(
    context: Annotated[Context, TaskiqDepends()],
) -> dict[str, Any]:
    """Check for provider tokens expiring within threshold.

    Runs every 15 minutes via scheduler. Finds active provider connections
    with credentials expiring within the configured threshold and emits
    ProviderTokenExpiringSoon domain events for each.

    Args:
        context: TaskIQ context with injected dependencies.
            - context.state.database: Database instance for sessions.

    Returns:
        Dict with counts: {"checked": N, "expiring": M, "notified": K}

    Example:
        # Enqueue manually (for testing)
        await check_expiring_tokens.kiq()

        # Scheduled via cron (production)
        # See scheduler.py for cron configuration
    """
    threshold_hours = _settings.token_expiry_threshold_hours

    logger.info(
        "check_expiring_tokens_started",
        threshold_hours=threshold_hours,
    )

    async with context.state.database.get_session() as session:
        repo = ProviderConnectionRepository(session)

        # Query for expiring connections
        expiring = await repo.find_expiring_soon(hours=threshold_hours)
        total_active = await repo.count_active()

        # Emit events for each expiring connection
        # Note: Event bus integration will be added in Phase 6 (API Integration)
        # For now, we log the events that would be published
        notified = 0
        for conn in expiring:
            event = ProviderTokenExpiringSoon(
                connection_id=conn.id,
                user_id=conn.user_id,
                provider_slug=conn.provider_slug,
                expires_at=conn.credentials_expires_at,
            )

            # TODO: Phase 6 - Publish via event bus for SSE delivery
            # await context.state.event_bus.publish(event)

            logger.info(
                "token_expiring_soon",
                connection_id=str(event.connection_id),
                user_id=str(event.user_id),
                provider_slug=event.provider_slug,
                expires_at=event.expires_at.isoformat(),
            )
            notified += 1

    result = {
        "checked": total_active,
        "expiring": len(expiring),
        "notified": notified,
    }

    logger.info(
        "check_expiring_tokens_completed",
        **result,
    )

    return result
