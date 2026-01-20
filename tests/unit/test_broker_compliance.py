"""Broker compliance tests.

Verifies that expected tasks are registered with the broker.
This catches issues where tasks are defined but not imported/registered.

Reference:
    - docs/architecture/background-jobs.md (Lines 270-278)
"""

import pytest

# Import tasks module to ensure registration
from dashtam_jobs import tasks  # noqa: F401
from dashtam_jobs.broker import broker
from dashtam_jobs.tasks.tokens import check_expiring_tokens


@pytest.mark.unit
def test_check_expiring_tokens_task_exists() -> None:
    """Verify check_expiring_tokens task is properly defined.

    This test ensures the task is properly decorated and importable.
    """
    # Task should be importable and have broker attached
    assert check_expiring_tokens is not None
    assert hasattr(check_expiring_tokens, "kiq"), "Task missing kiq method"


@pytest.mark.unit
def test_check_expiring_tokens_task_has_labels() -> None:
    """Verify check_expiring_tokens task has correct labels."""
    # TaskIQ stores custom labels nested under 'labels' key
    task_labels = check_expiring_tokens.labels
    assert task_labels is not None

    # Custom labels are nested under 'labels' key
    custom_labels = task_labels.get("labels", {})
    assert custom_labels.get("category") == "provider"
    assert "schedule" in custom_labels


@pytest.mark.unit
def test_broker_has_result_backend() -> None:
    """Verify broker is configured with result backend."""
    # The broker should have a result backend configured
    assert broker.result_backend is not None


@pytest.mark.unit
def test_broker_has_middlewares() -> None:
    """Verify broker has logging middleware registered."""
    from dashtam_jobs.middlewares.logging import JobLoggingMiddleware

    # Check that middlewares are registered
    assert broker.middlewares is not None
    assert len(broker.middlewares) > 0

    # Verify JobLoggingMiddleware is among them
    middleware_types = [type(m) for m in broker.middlewares]
    assert JobLoggingMiddleware in middleware_types
