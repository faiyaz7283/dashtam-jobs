"""Unit tests for SSE publisher."""

import json
from unittest.mock import AsyncMock
from uuid import UUID

import pytest
from redis.exceptions import RedisError

from dashtam_jobs.infrastructure.sse_publisher import SSEPublisher


@pytest.fixture
def mock_redis() -> AsyncMock:
    """Create a mock Redis client."""
    return AsyncMock()


@pytest.fixture
def publisher(mock_redis: AsyncMock) -> SSEPublisher:
    """Create an SSE publisher with mock Redis."""
    return SSEPublisher(mock_redis)


class TestSSEPublisher:
    """Tests for SSEPublisher class."""

    @pytest.mark.anyio
    async def test_publish_to_user_correct_channel(
        self, publisher: SSEPublisher, mock_redis: AsyncMock
    ) -> None:
        """Should publish to the correct user channel."""
        user_id = UUID("01234567-89ab-cdef-0123-456789abcdef")

        await publisher.publish_to_user(
            user_id=user_id,
            event_type="provider.token.expiring",
            data={"connection_id": "abc123"},
        )

        mock_redis.publish.assert_called_once()
        call_args = mock_redis.publish.call_args
        channel = call_args[0][0]

        assert channel == f"sse:user:{user_id}"

    @pytest.mark.anyio
    async def test_publish_to_user_correct_event_structure(
        self, publisher: SSEPublisher, mock_redis: AsyncMock
    ) -> None:
        """Should publish event with correct JSON structure."""
        user_id = UUID("01234567-89ab-cdef-0123-456789abcdef")

        await publisher.publish_to_user(
            user_id=user_id,
            event_type="provider.token.expiring",
            data={"connection_id": "abc123", "provider_slug": "plaid"},
        )

        call_args = mock_redis.publish.call_args
        event_json = call_args[0][1]
        event = json.loads(event_json)

        assert event["event_type"] == "provider.token.expiring"
        assert event["user_id"] == str(user_id)
        assert event["data"]["connection_id"] == "abc123"
        assert event["data"]["provider_slug"] == "plaid"
        assert "event_id" in event
        assert "occurred_at" in event

    @pytest.mark.anyio
    async def test_publish_to_user_fail_open_on_redis_error(
        self, publisher: SSEPublisher, mock_redis: AsyncMock
    ) -> None:
        """Should not raise exception on Redis error (fail-open)."""
        mock_redis.publish.side_effect = RedisError("Connection refused")
        user_id = UUID("01234567-89ab-cdef-0123-456789abcdef")

        # Should not raise
        await publisher.publish_to_user(
            user_id=user_id,
            event_type="provider.token.expiring",
            data={"test": True},
        )

    @pytest.mark.anyio
    async def test_broadcast_correct_channel(
        self, publisher: SSEPublisher, mock_redis: AsyncMock
    ) -> None:
        """Should broadcast to the correct channel."""
        await publisher.broadcast(
            event_type="system.maintenance",
            data={"message": "Scheduled maintenance"},
        )

        mock_redis.publish.assert_called_once()
        call_args = mock_redis.publish.call_args
        channel = call_args[0][0]

        assert channel == "sse:broadcast"

    @pytest.mark.anyio
    async def test_broadcast_uses_nil_uuid_when_no_user_id(
        self, publisher: SSEPublisher, mock_redis: AsyncMock
    ) -> None:
        """Should use nil UUID when no system_user_id provided."""
        await publisher.broadcast(
            event_type="system.maintenance",
            data={"message": "test"},
        )

        call_args = mock_redis.publish.call_args
        event = json.loads(call_args[0][1])

        assert event["user_id"] == "00000000-0000-0000-0000-000000000000"

    @pytest.mark.anyio
    async def test_broadcast_uses_provided_user_id(
        self, publisher: SSEPublisher, mock_redis: AsyncMock
    ) -> None:
        """Should use provided system_user_id when given."""
        system_user_id = UUID("11111111-1111-1111-1111-111111111111")

        await publisher.broadcast(
            event_type="system.maintenance",
            data={"message": "test"},
            system_user_id=system_user_id,
        )

        call_args = mock_redis.publish.call_args
        event = json.loads(call_args[0][1])

        assert event["user_id"] == str(system_user_id)

    @pytest.mark.anyio
    async def test_broadcast_fail_open_on_redis_error(
        self, publisher: SSEPublisher, mock_redis: AsyncMock
    ) -> None:
        """Should not raise exception on Redis error (fail-open)."""
        mock_redis.publish.side_effect = RedisError("Connection refused")

        # Should not raise
        await publisher.broadcast(
            event_type="system.maintenance",
            data={"test": True},
        )

    @pytest.mark.anyio
    async def test_close_calls_redis_aclose(
        self, publisher: SSEPublisher, mock_redis: AsyncMock
    ) -> None:
        """Should close the Redis connection."""
        await publisher.close()
        mock_redis.aclose.assert_called_once()

    def test_channel_prefix_matches_api(self, publisher: SSEPublisher) -> None:
        """Channel prefix should match dashtam-api's SSE_CHANNEL_PREFIX."""
        # This value must match dashtam-api/src/core/constants.py SSE_CHANNEL_PREFIX
        assert publisher.CHANNEL_PREFIX == "sse"
