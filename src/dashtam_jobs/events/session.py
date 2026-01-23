"""Session-related domain events.

Events emitted by background jobs related to user sessions.
These follow the same pattern as dashtam-api's domain events.

Reference:
    - dashtam-api/src/domain/events/session_events.py
    - dashtam-api/docs/architecture/sse-architecture.md Section 3.6
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID, uuid4


@dataclass(frozen=True, kw_only=True)
class SessionExpiringSoon:
    """User session expiring soon.

    Emitted by check_expiring_sessions job when a user's session is
    expiring within the configured threshold.

    This event triggers SSE notification to the user via
    SSEEventType.SECURITY_SESSION_EXPIRING in dashtam-api.

    Attributes:
        event_id: Unique identifier for this event instance.
        occurred_at: Timestamp when the event occurred (UTC).
        session_id: Session that is expiring soon.
        user_id: User who owns this session.
        expires_at: When the session will expire.

    Example:
        event = SessionExpiringSoon(
            session_id=session.id,
            user_id=session.user_id,
            expires_at=session.expires_at,
        )
        await sse_publisher.publish_to_user(...)
    """

    # Event metadata (auto-generated)
    event_id: UUID = field(default_factory=uuid4)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    # Event payload
    session_id: UUID
    user_id: UUID
    expires_at: datetime
