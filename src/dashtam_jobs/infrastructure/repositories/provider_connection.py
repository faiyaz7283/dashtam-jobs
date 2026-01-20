"""Provider connection repository for background jobs.

Thin repository implementation that queries the same database as the API.
Uses raw SQL to avoid duplicating model definitions.

This follows the architecture principle: "jobs orchestrate, don't implement"
- We only query what's needed to emit events
- No domain mapping (that's API's responsibility)

Reference:
    - dashtam-api/src/infrastructure/persistence/repositories/provider_connection_repository.py
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True)
class ExpiringConnection:
    """DTO for connections with expiring credentials.

    Contains only the fields needed to emit ProviderTokenExpiringSoon events.

    Attributes:
        id: Connection's unique identifier.
        user_id: User who owns this connection.
        provider_slug: Provider identifier (e.g., "schwab").
        credentials_expires_at: When credentials expire.
    """

    id: UUID
    user_id: UUID
    provider_slug: str
    credentials_expires_at: datetime


class ProviderConnectionRepository:
    """Thin repository for provider connection queries.

    This is a thin adapter that provides only the queries needed by
    background jobs. It uses raw SQL to avoid model duplication.

    Attributes:
        session: SQLAlchemy async session.

    Example:
        async with db.get_session() as session:
            repo = ProviderConnectionRepository(session)
            expiring = await repo.find_expiring_soon(hours=24)
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository with database session.

        Args:
            session: SQLAlchemy async session.
        """
        self._session = session

    async def find_expiring_soon(
        self,
        hours: int = 24,
    ) -> list[ExpiringConnection]:
        """Find active connections with credentials expiring soon.

        Queries provider_connections table for active connections
        where credentials_expires_at is within the threshold.

        Args:
            hours: Time threshold in hours (default 24).

        Returns:
            List of ExpiringConnection DTOs for connections with
            credentials expiring within the threshold.
        """
        threshold = datetime.now(UTC) + timedelta(hours=hours)

        query = text("""
            SELECT id, user_id, provider_slug, credentials_expires_at
            FROM provider_connections
            WHERE status = 'active'
              AND credentials_expires_at IS NOT NULL
              AND credentials_expires_at <= :threshold
            ORDER BY credentials_expires_at ASC
        """)

        result = await self._session.execute(query, {"threshold": threshold})
        rows = result.fetchall()

        return [
            ExpiringConnection(
                id=row.id,
                user_id=row.user_id,
                provider_slug=row.provider_slug,
                credentials_expires_at=row.credentials_expires_at,
            )
            for row in rows
        ]

    async def count_active(self) -> int:
        """Count total active connections.

        Returns:
            Number of active connections in the database.
        """
        query = text("""
            SELECT COUNT(*) FROM provider_connections WHERE status = 'active'
        """)

        result = await self._session.execute(query)
        count: int = result.scalar_one()
        return count
