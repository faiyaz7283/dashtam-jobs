"""TaskIQ broker configuration.

This module configures the central broker instance connecting to Redis
for task queuing and result storage.
"""

from taskiq import TaskiqEvents, TaskiqState
from taskiq_redis import ListQueueBroker, RedisAsyncResultBackend

from dashtam_jobs.core.logging import configure_logging, get_logger
from dashtam_jobs.core.settings import get_settings
from dashtam_jobs.middlewares.logging import JobLoggingMiddleware

logger = get_logger(__name__)

# Get settings lazily
_settings = get_settings()

# Broker for task queuing with middleware
broker = (
    ListQueueBroker(
        url=_settings.redis_url,
        queue_name="dashtam:jobs",
    )
    .with_result_backend(
        RedisAsyncResultBackend(
            redis_url=_settings.redis_url,
            result_ex_time=_settings.job_result_ttl,
        )
    )
    .with_middlewares(
        JobLoggingMiddleware(),
    )
)


@broker.on_event(TaskiqEvents.WORKER_STARTUP)
async def startup(state: TaskiqState) -> None:
    """Initialize resources shared across all task executions.

    This runs ONCE when the worker process starts, not per-task.
    Resources are stored in `state` and accessed via TaskiqDepends.

    Args:
        state: TaskIQ state object for storing shared resources.
    """
    configure_logging()
    logger.info("worker_startup")

    # Import here to avoid circular imports and allow lazy loading
    from redis.asyncio import Redis

    from dashtam_jobs.infrastructure.database import Database
    from dashtam_jobs.infrastructure.sse_publisher import SSEPublisher

    # Database instance (manages engine and sessions)
    state.database = Database(_settings.database_url)

    # SSE publisher for sending notifications to API clients
    # Uses the same Redis that the API uses for SSE pub/sub
    state.sse_redis = Redis.from_url(_settings.redis_url)
    state.sse_publisher = SSEPublisher(state.sse_redis)

    logger.info(
        "worker_startup_complete",
        database_url=_settings.database_url[:20] + "...",  # Truncate for safety
    )


@broker.on_event(TaskiqEvents.WORKER_SHUTDOWN)
async def shutdown(state: TaskiqState) -> None:
    """Clean up resources when worker shuts down.

    Args:
        state: TaskIQ state object containing shared resources.
    """
    logger.info("worker_shutdown")

    # Close database connections
    if hasattr(state, "database") and state.database is not None:
        await state.database.close()
        logger.info("worker_database_closed")

    # Close SSE publisher Redis connection
    if hasattr(state, "sse_publisher") and state.sse_publisher is not None:
        await state.sse_publisher.close()
        logger.info("worker_sse_publisher_closed")

    logger.info("worker_shutdown_complete")
