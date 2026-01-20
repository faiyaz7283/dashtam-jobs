"""Database connection and session management.

This module provides database connection management using SQLAlchemy's
async engine and session handling for the jobs worker.

The jobs worker connects to the same PostgreSQL database as the API
but manages its own connection pool.

Reference:
    - dashtam-api/src/infrastructure/persistence/database.py
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


class Database:
    """Database connection and session management for jobs worker.

    This class manages the database engine and provides async sessions
    for database operations within tasks.

    Attributes:
        engine: SQLAlchemy async engine.
        async_session: Session factory for creating sessions.

    Example:
        db = Database("postgresql+asyncpg://user:pass@host/dbname")
        async with db.get_session() as session:
            # Use session for database operations
    """

    def __init__(
        self,
        database_url: str,
        echo: bool = False,
        pool_size: int = 5,
        max_overflow: int = 10,
    ) -> None:
        """Initialize database with connection parameters.

        Args:
            database_url: Database connection URL (e.g., postgresql+asyncpg://...).
            echo: If True, log all SQL statements (useful for debugging).
            pool_size: Number of connections to maintain in pool.
            max_overflow: Maximum overflow connections above pool_size.
        """
        self.engine: AsyncEngine = create_async_engine(
            database_url,
            echo=echo,
            pool_pre_ping=True,
            pool_size=pool_size,
            max_overflow=max_overflow,
            connect_args=(
                {
                    "server_settings": {"jit": "off"},
                    "command_timeout": 60,
                    "timeout": 30,
                }
                if "postgresql" in database_url
                else {}
            ),
        )

        self.async_session = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

    @asynccontextmanager
    async def get_session(self) -> AsyncGenerator[AsyncSession]:
        """Provide a transactional database session.

        Yields:
            AsyncSession: Database session for operations.

        Example:
            async with db.get_session() as session:
                result = await session.execute(query)
        """
        async with self.async_session() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()

    async def close(self) -> None:
        """Close all database connections.

        Should be called when shutting down the worker.
        """
        await self.engine.dispose()

    async def check_connection(self) -> bool:
        """Check if database connection is working.

        Returns:
            bool: True if connection is successful, False otherwise.
        """
        try:
            async with self.get_session() as session:
                await session.execute(text("SELECT 1"))
                return True
        except Exception:
            return False
