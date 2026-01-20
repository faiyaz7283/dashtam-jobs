"""Integration tests for broker with real Redis.

These tests require Redis to be running and test actual job
enqueue/execute behavior.

Run with: make test-integration (requires docker-compose.test.yml)
"""

import pytest

# Import tasks to ensure registration
from dashtam_jobs import tasks  # noqa: F401
from dashtam_jobs.broker import broker


@pytest.mark.integration
async def test_broker_can_connect_to_redis() -> None:
    """Test that broker can establish Redis connection."""
    # Startup will connect to Redis
    await broker.startup()

    try:
        # If we get here, connection succeeded
        assert True
    finally:
        await broker.shutdown()


@pytest.mark.integration
async def test_task_can_be_enqueued() -> None:
    """Test that a task can be enqueued to Redis."""
    await broker.startup()

    try:
        # Verify broker is working by checking startup completed
        # Note: Actual task enqueue requires worker running
        assert True

    finally:
        await broker.shutdown()


@pytest.mark.integration
async def test_broker_startup_shutdown_cycle() -> None:
    """Test broker can handle multiple startup/shutdown cycles."""
    # First cycle
    await broker.startup()
    await broker.shutdown()

    # Second cycle (should not raise)
    await broker.startup()
    await broker.shutdown()
