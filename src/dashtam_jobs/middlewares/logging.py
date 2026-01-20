"""Job execution logging middleware.

Provides structured logging for all job executions including
start, completion, and failure events.
"""

from typing import Any

from taskiq import TaskiqMessage, TaskiqMiddleware, TaskiqResult

from dashtam_jobs.core.logging import get_logger

logger = get_logger(__name__)


class JobLoggingMiddleware(TaskiqMiddleware):
    """Structured logging for all job executions.

    Logs are written to stdout in JSON format, picked up by
    container logging (Docker, CloudWatch, etc.).
    """

    async def pre_execute(self, message: TaskiqMessage) -> TaskiqMessage:
        """Log when job starts.

        Args:
            message: TaskIQ message containing job details.

        Returns:
            Unmodified message for continued processing.
        """
        logger.info(
            "job_started",
            job_id=message.task_id,
            task_name=message.task_name,
            args=str(message.args)[:100],  # Truncate for safety
            labels=message.labels,
        )
        return message

    async def post_execute(
        self,
        message: TaskiqMessage,
        result: TaskiqResult[Any],
    ) -> None:
        """Log when job completes (success or failure).

        Args:
            message: TaskIQ message containing job details.
            result: TaskIQ result containing execution outcome.
        """
        log_data = {
            "job_id": message.task_id,
            "task_name": message.task_name,
            "execution_time_seconds": result.execution_time,
            "is_error": result.is_err,
        }

        if result.is_err:
            log_data["error"] = str(result.error)[:500]
            logger.error("job_failed", **log_data)
        else:
            logger.info("job_completed", **log_data)
