# Cross-Service SSE Publishing

This guide explains how `dashtam-jobs` can publish Server-Sent Events (SSE) to clients connected to `dashtam-api`.

## Overview

The API's SSE infrastructure uses Redis pub/sub for real-time event delivery. Background jobs can publish events directly to the same Redis channels, and connected clients receive them instantly.

```text
┌─────────────────┐                    ┌─────────────────┐
│  dashtam-jobs   │                    │   dashtam-api   │
│                 │                    │                 │
│ Task publishes  │                    │ Client connected│
│ SSE event       │                    │ via GET /events │
│       ↓         │                    │       ↑         │
│ Redis PUBLISH   │────── Redis ──────▶│ RedisSSE-       │
│ to user channel │                    │ Subscriber      │
│                 │                    │ delivers event  │
└─────────────────┘                    └─────────────────┘
```

**Key insight**: Jobs don't need to call an API endpoint. They publish directly to Redis, and the API's existing subscriber infrastructure delivers to clients.

---

## Channel Naming Convention

The API uses these Redis channel patterns:

| Channel | Pattern | Purpose |
| --------- | --------- | --------- |
| User channel | `sse:user:{user_id}` | Events for a specific user |
| Broadcast | `sse:broadcast` | Events for all connected users |

**Examples**:

- `sse:user:01234567-89ab-cdef-0123-456789abcdef`
- `sse:broadcast`

---

## Event JSON Format

Events must be JSON with this exact structure:

```json
{
  "event_id": "01958f12-3456-7890-abcd-ef0123456789",
  "event_type": "provider.token.expiring",
  "user_id": "01234567-89ab-cdef-0123-456789abcdef",
  "data": {
    "connection_id": "abcd1234-...",
    "provider_slug": "plaid",
    "expires_at": "2026-01-21T00:00:00+00:00"
  },
  "occurred_at": "2026-01-20T02:30:00+00:00"
}
```

| Field | Type | Description |
| ------- | ------ | ------------- |
| `event_id` | UUID string | Unique identifier (UUID v7 recommended for ordering) |
| `event_type` | string | SSE event type (see below) |
| `user_id` | UUID string | Target user |
| `data` | object | Event-specific payload |
| `occurred_at` | ISO 8601 | When the event occurred (UTC) |

---

## Available Event Types

Jobs should only publish events that make sense as background notifications:

| Event Type | Category | Description |
| ------------ | ---------- | ------------- |
| `provider.token.expiring` | provider | Token expires within threshold |
| `security.session.expiring` | security | Session expires within threshold |

**Note**: Other provider events (`provider.token.refreshed`, `provider.token.failed`, `provider.disconnected`) and security events (`security.session.*`, `security.password.*`, `security.login.failed`) are triggered by user actions in the API, not background jobs.

---

## Implementation

### 1. SSE Publisher Utility

Create a simple publisher in `dashtam-jobs`:

```python
# src/dashtam_jobs/infrastructure/sse_publisher.py

import json
from datetime import UTC, datetime
from uuid import UUID

from redis.asyncio import Redis
from uuid_extensions import uuid7


class SSEPublisher:
    """Publish SSE events to dashtam-api's Redis channels.
    
    This allows background jobs to send real-time notifications
    to connected clients without calling an API endpoint.
    """
    
    CHANNEL_PREFIX = "sse"
    
    def __init__(self, redis_client: Redis) -> None:
        self._redis = redis_client
    
    async def publish_to_user(
        self,
        user_id: UUID,
        event_type: str,
        data: dict,
    ) -> None:
        """Publish SSE event to a specific user.
        
        Args:
            user_id: Target user's UUID.
            event_type: SSE event type (e.g., "provider.token.expiring").
            data: Event payload (will be JSON serialized).
        """
        channel = f"{self.CHANNEL_PREFIX}:user:{user_id}"
        
        event = {
            "event_id": str(uuid7()),
            "event_type": event_type,
            "user_id": str(user_id),
            "data": data,
            "occurred_at": datetime.now(UTC).isoformat(),
        }
        
        await self._redis.publish(channel, json.dumps(event))
    
    async def broadcast(
        self,
        event_type: str,
        data: dict,
        system_user_id: UUID | None = None,
    ) -> None:
        """Broadcast SSE event to all connected users.
        
        Args:
            event_type: SSE event type.
            data: Event payload.
            system_user_id: Optional user ID for event (use system UUID if none).
        """
        channel = f"{self.CHANNEL_PREFIX}:broadcast"
        
        event = {
            "event_id": str(uuid7()),
            "event_type": event_type,
            "user_id": str(system_user_id) if system_user_id else "00000000-0000-0000-0000-000000000000",
            "data": data,
            "occurred_at": datetime.now(UTC).isoformat(),
        }
        
        await self._redis.publish(channel, json.dumps(event))
```

### 2. Worker Startup Integration

Add SSE publisher to worker state:

```python
# src/dashtam_jobs/broker.py

@broker.on_event(TaskiqEvents.WORKER_STARTUP)
async def startup(state: TaskiqState) -> None:
    # ... existing database setup ...
    
    # SSE publisher for sending notifications to API clients
    from redis.asyncio import Redis
    from dashtam_jobs.infrastructure.sse_publisher import SSEPublisher
    
    redis_client = Redis.from_url(_settings.redis_url)
    state.sse_publisher = SSEPublisher(redis_client)


@broker.on_event(TaskiqEvents.WORKER_SHUTDOWN)
async def shutdown(state: TaskiqState) -> None:
    # ... existing cleanup ...
    
    if hasattr(state, "sse_publisher"):
        await state.sse_publisher._redis.aclose()
```

### 3. Using in Tasks

```python
# src/dashtam_jobs/tasks/tokens.py

@broker.task(...)
async def check_expiring_tokens(
    context: Annotated[Context, TaskiqDepends()],
) -> dict[str, Any]:
    """Check for expiring tokens and notify users via SSE."""
    
    async with context.state.database.get_session() as session:
        repo = ProviderConnectionRepository(session)
        expiring = await repo.find_expiring_soon(hours=24)
        
        sse_publisher = context.state.sse_publisher
        
        for conn in expiring:
            # Publish SSE event directly to user's channel
            await sse_publisher.publish_to_user(
                user_id=conn.user_id,
                event_type="provider.token.expiring",
                data={
                    "connection_id": str(conn.id),
                    "provider_slug": conn.provider_slug,
                    "expires_at": conn.credentials_expires_at.isoformat(),
                },
            )
        
        return {"checked": total, "expiring": len(expiring), "notified": len(expiring)}
```

---

## Configuration

Jobs need access to the **same Redis** that the API uses for SSE. Configure via environment:

```bash
# env/.env.dev

# Use the API's Redis (or a shared Redis instance)
# This must be the same Redis the API uses for SSE pub/sub
REDIS_URL=redis://dashtam-dev-redis:6379/0
```

**Important**: If jobs use a separate Redis instance, SSE events won't reach API clients.

---

## Testing

### Unit Test (Mock Redis)

```python
@pytest.mark.anyio
async def test_sse_publisher_publishes_to_correct_channel():
    mock_redis = AsyncMock()
    publisher = SSEPublisher(mock_redis)
    
    user_id = UUID("01234567-89ab-cdef-0123-456789abcdef")
    await publisher.publish_to_user(
        user_id=user_id,
        event_type="provider.token.expiring",
        data={"connection_id": "abc"},
    )
    
    mock_redis.publish.assert_called_once()
    call_args = mock_redis.publish.call_args
    
    # Verify channel
    assert call_args[0][0] == f"sse:user:{user_id}"
    
    # Verify event structure
    event = json.loads(call_args[0][1])
    assert event["event_type"] == "provider.token.expiring"
    assert event["user_id"] == str(user_id)
    assert event["data"]["connection_id"] == "abc"
```

### Integration Test (Real Redis)

```python
@pytest.mark.integration
@pytest.mark.anyio
async def test_sse_event_reaches_subscriber(redis_client):
    """Verify event published by jobs reaches API's subscriber pattern."""
    publisher = SSEPublisher(redis_client)
    user_id = uuid7()
    channel = f"sse:user:{user_id}"
    
    # Subscribe (simulating API's RedisSSESubscriber)
    pubsub = redis_client.pubsub()
    await pubsub.subscribe(channel)
    
    # Publish event
    await publisher.publish_to_user(
        user_id=user_id,
        event_type="provider.token.expiring",
        data={"test": True},
    )
    
    # Receive event
    message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=5)
    assert message is not None
    
    event = json.loads(message["data"])
    assert event["event_type"] == "provider.token.expiring"
    
    await pubsub.unsubscribe(channel)
```

---

## Error Handling

Follow fail-open pattern (consistent with API's SSEPublisher):

```python
async def publish_to_user(self, ...) -> None:
    try:
        await self._redis.publish(channel, json.dumps(event))
        logger.info("sse_event_published", user_id=str(user_id), event_type=event_type)
    except RedisError as e:
        # Fail-open: log but don't raise
        logger.warning(
            "sse_publish_failed",
            user_id=str(user_id),
            event_type=event_type,
            error=str(e),
        )
```

**Why fail-open?** SSE notifications are best-effort. A failed notification shouldn't crash the job or prevent other work.

---

## Reference

- **API SSE Architecture**: `dashtam-api/docs/architecture/sse-architecture.md`
- **API Channel Keys**: `dashtam-api/src/infrastructure/sse/channel_keys.py`
- **API Publisher**: `dashtam-api/src/infrastructure/sse/redis_publisher.py`
- **SSE Event Types**: `dashtam-api/src/domain/events/sse_event.py`

---

**Created**: 2026-01-20 | **Last Updated**: 2026-01-20
