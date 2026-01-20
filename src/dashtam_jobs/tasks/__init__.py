"""Task definitions for dashtam-jobs.

All background tasks are defined in this package and registered with the broker.

Tasks are automatically registered with the broker via the @broker.task decorator.
Import this module to ensure all tasks are registered.
"""

# Re-export tasks for easy importing and to ensure registration
from dashtam_jobs.tasks.tokens import check_expiring_tokens

__all__ = ["check_expiring_tokens"]
