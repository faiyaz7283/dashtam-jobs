"""TaskIQ scheduler configuration.

This module configures the scheduler for cron-based and time-based job execution.
"""

from taskiq import TaskiqScheduler
from taskiq_redis import RedisScheduleSource

from dashtam_jobs.broker import broker
from dashtam_jobs.core.settings import get_settings

# Get settings lazily
_settings = get_settings()

# Schedule source stores scheduled tasks in Redis
schedule_source = RedisScheduleSource(_settings.redis_url)

# Scheduler manages execution timing
scheduler = TaskiqScheduler(
    broker=broker,
    sources=[schedule_source],
)
