import logging
from typing import Any

logger = logging.getLogger("app.metrics")


def log_request_metric(
    *,
    method: str,
    path: str,
    status_code: int,
    response_time_ms: float,
    user_id: int | None,
    role: str | None,
    records_count: int | None,
    error: str | None,
    queue_job_id: str | None = None,
    queue_status: str | None = None,
) -> None:
    payload: dict[str, Any] = {
        "user_id": user_id,
        "role": role,
        "records_count": records_count,
        "error": error,
        "queue_job_id": queue_job_id,
        "queue_status": queue_status,
    }
    logger.info(
        "request_metrics %s %s -> %s in %.2fms %s",
        method,
        path,
        status_code,
        round(response_time_ms, 2),
        payload,
    )


def log_queue_metric(
    *,
    queue_job_id: str,
    queue_status: str,
    error: str | None,
) -> None:
    logger.info(
        "queue_metrics %s",
        {
            "queue_job_id": queue_job_id,
            "queue_status": queue_status,
            "error": error,
        },
    )
