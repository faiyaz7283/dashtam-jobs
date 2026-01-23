"""Domain events for background jobs.

This module defines domain events that jobs emit. These are minimal,
local definitions to avoid coupling with dashtam-api.

Future exploration: Create shared event package if event count grows.
See: Plan "Open Decisions" section.

Reference:
    - docs/architecture/background-jobs.md (Lines 450-495)
"""

from dashtam_jobs.events.provider import ProviderTokenExpiringSoon
from dashtam_jobs.events.session import SessionExpiringSoon

__all__ = ["ProviderTokenExpiringSoon", "SessionExpiringSoon"]
