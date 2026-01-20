"""SSE Publisher for cross-service event delivery.

Publishes SSE events to dashtam-api's Redis pub/sub channels,
allowing background jobs to send real-time notifications to
connected clients without calling an API endpoint.

Reference:
    - docs/guides/cross-service-sse-publishing.md
    - dashtam-api/src/infrastructure/sse/redis_publisher.py
"""

import json
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from redis.asyncio import Redis
from redis.exceptions import RedisError
from uuid_extensions import uuid7  # provided by uuid7 package

from dashtam_jobs.core.logging import get_logger

logger = get_logger(__name__)


class SSEPublisher:
    """Publish SSE events to dashtam-api's Redis channels.

    This allows background jobs to send real-time notifications
    to connected clients without calling an API endpoint.

    The publisher uses the same Redis pub/sub channels that the API's
    RedisSSESubscriber listens to, enabling seamless cross-service
    event delivery.

    Attributes:
        CHANNEL_PREFIX: Redis channel prefix (must match API's SSE_CHANNEL_PREFIX).

    Example:
        publisher = SSEPublisher(redis_client)
        await publisher.publish_to_user(
            user_id=user_id,
            event_type="provider.token.expiring",
            data={"connection_id": str(conn_id), "provider_slug": "plaid"},
        )
    """

    CHANNEL_PREFIX = "sse"
    """Redis channel prefix - must match dashtam-api's SSE_CHANNEL_PREFIX."""

    def __init__(self, redis_client: Redis[bytes]) -> None:  # type: ignore[type-arg]
        """Initialize SSE publisher.

        Args:
            redis_client: Async Redis client instance.
        """
        self._redis = redis_client

    async def publish_to_user(
        self,
        user_id: UUID,
        event_type: str,
        data: dict[str, Any],
    ) -> None:
        """Publish SSE event to a specific user.

        The event is published to the user's Redis pub/sub channel,
        where the API's RedisSSESubscriber will receive and deliver
        it to the connected client.

        Args:
            user_id: Target user's UUID.
            event_type: SSE event type (e.g., "provider.token.expiring").
            data: Event payload (will be JSON serialized).

        Note:
            Fail-open: Redis errors are logged but not raised.
            SSE notifications are best-effort.
        """
        channel = f"{self.CHANNEL_PREFIX}:user:{user_id}"

        event = {
            "event_id": str(uuid7()),
            "event_type": event_type,
            "user_id": str(user_id),
            "data": data,
            "occurred_at": datetime.now(UTC).isoformat(),
        }

        try:
            await self._redis.publish(channel, json.dumps(event))
            logger.info(
                "sse_event_published",
                user_id=str(user_id),
                event_type=event_type,
                channel=channel,
            )
        except RedisError as e:
            # Fail-open: log but don't raise
            logger.warning(
                "sse_publish_failed",
                user_id=str(user_id),
                event_type=event_type,
                error=str(e),
            )

    async def broadcast(
        self,
        event_type: str,
        data: dict[str, Any],
        system_user_id: UUID | None = None,
    ) -> None:
        """Broadcast SSE event to all connected users.

        The event is published to the broadcast channel, where all
        connected clients will receive it.

        Args:
            event_type: SSE event type.
            data: Event payload (will be JSON serialized).
            system_user_id: Optional user ID for event attribution.
                If not provided, uses a nil UUID.

        Note:
            Fail-open: Redis errors are logged but not raised.
        """
        channel = f"{self.CHANNEL_PREFIX}:broadcast"

        # Use nil UUID if no system user ID provided
        user_id_str = (
            str(system_user_id)
            if system_user_id
            else "00000000-0000-0000-0000-000000000000"
        )

        event = {
            "event_id": str(uuid7()),
            "event_type": event_type,
            "user_id": user_id_str,
            "data": data,
            "occurred_at": datetime.now(UTC).isoformat(),
        }

        try:
            await self._redis.publish(channel, json.dumps(event))
            logger.info(
                "sse_event_broadcast",
                event_type=event_type,
                channel=channel,
            )
        except RedisError as e:
            # Fail-open: log but don't raise
            logger.warning(
                "sse_broadcast_failed",
                event_type=event_type,
                error=str(e),
            )

    async def close(self) -> None:
        """Close the Redis connection.

        Should be called during worker shutdown.
        """
        await self._redis.aclose()
