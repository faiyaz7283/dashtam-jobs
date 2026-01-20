"""Provider-related domain events.

Events emitted by background jobs related to provider connections.
These follow the same pattern as dashtam-api's domain events.

Reference:
    - dashtam-api/src/domain/events/provider_events.py
    - dashtam-api/src/domain/events/base_event.py
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID, uuid4


@dataclass(frozen=True, kw_only=True)
class ProviderTokenExpiringSoon:
    """Provider OAuth token expiring soon.

    Emitted by check_expiring_tokens job when a provider connection's
    credentials are expiring within the configured threshold.

    This event triggers SSE notification to the user via
    SSEEventType.PROVIDER_TOKEN_EXPIRING in dashtam-api.

    Attributes:
        event_id: Unique identifier for this event instance.
        occurred_at: Timestamp when the event occurred (UTC).
        connection_id: Provider connection with expiring credentials.
        user_id: User who owns this connection.
        provider_slug: Provider identifier (e.g., "schwab").
        expires_at: When the credentials will expire.

    Example:
        event = ProviderTokenExpiringSoon(
            connection_id=conn.id,
            user_id=conn.user_id,
            provider_slug=conn.provider_slug,
            expires_at=conn.credentials_expires_at,
        )
        await event_bus.publish(event)
    """

    # Event metadata (auto-generated)
    event_id: UUID = field(default_factory=uuid4)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    # Event payload
    connection_id: UUID
    user_id: UUID
    provider_slug: str
    expires_at: datetime
