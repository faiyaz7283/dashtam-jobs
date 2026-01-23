"""Session repository for background jobs.

Thin repository implementation that queries the same database as the API.
Uses raw SQL to avoid duplicating model definitions.

This follows the architecture principle: "jobs orchestrate, don't implement"
- We only query what's needed to emit events
- No domain mapping (that's API's responsibility)

Reference:
    - dashtam-api/src/infrastructure/persistence/repositories/session_repository.py
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True)
class ExpiringSession:
    """DTO for sessions expiring soon.

    Contains only the fields needed to emit SessionExpiringSoon events.

    Attributes:
        id: Session's unique identifier.
        user_id: User who owns this session.
        expires_at: When session expires.
    """

    id: UUID
    user_id: UUID
    expires_at: datetime


class SessionRepository:
    """Thin repository for session queries.

    This is a thin adapter that provides only the queries needed by
    background jobs. It uses raw SQL to avoid model duplication.

    Attributes:
        session: SQLAlchemy async session.

    Example:
        async with db.get_session() as session:
            repo = SessionRepository(session)
            expiring = await repo.find_expiring_soon(minutes=15)
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository with database session.

        Args:
            session: SQLAlchemy async session.
        """
        self._session = session

    async def find_expiring_soon(
        self,
        minutes: int = 15,
    ) -> list[ExpiringSession]:
        """Find active sessions expiring soon.

        Queries sessions table for sessions where expires_at is within
        the threshold and revoked_at is NULL (not revoked).

        Args:
            minutes: Time threshold in minutes (default 15).

        Returns:
            List of ExpiringSession DTOs for sessions expiring
            within the threshold.
        """
        now = datetime.now(UTC)
        threshold = now + timedelta(minutes=minutes)

        query = text("""
            SELECT id, user_id, expires_at
            FROM sessions
            WHERE revoked_at IS NULL
              AND expires_at IS NOT NULL
              AND expires_at > :now
              AND expires_at <= :threshold
            ORDER BY expires_at ASC
        """)

        result = await self._session.execute(
            query,
            {"now": now, "threshold": threshold},
        )
        rows = result.fetchall()

        return [
            ExpiringSession(
                id=row.id,
                user_id=row.user_id,
                expires_at=row.expires_at,
            )
            for row in rows
        ]

    async def count_active(self) -> int:
        """Count total active (non-revoked, non-expired) sessions.

        Returns:
            Number of active sessions in the database.
        """
        now = datetime.now(UTC)

        query = text("""
            SELECT COUNT(*) FROM sessions
            WHERE revoked_at IS NULL
              AND (expires_at IS NULL OR expires_at > :now)
        """)

        result = await self._session.execute(query, {"now": now})
        count: int = result.scalar_one()
        return count
