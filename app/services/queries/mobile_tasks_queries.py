from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.cache import build_cache_key, cache
from app.core.config import settings
from app.schemas.bff import MobileTaskItem, MobileTaskSummary, MobileTasksResponse

STATUS_LABELS = {
    "CREATED": "Created",
    "ACTIVE": "In work",
    "COMPLETED": "Completed",
    "CANCELLED": "Cancelled",
}


def _iso(dt) -> str | None:
    if not dt:
        return None
    return dt.isoformat().replace("+00:00", "Z")


class MobileTasksQueryService:
    @staticmethod
    def get_tasks(
        db: Session,
        *,
        employee_id: int,
        role: str = "ENGINEER",
        account_type: str = "EMPLOYEE",
    ) -> MobileTasksResponse:
        key = build_cache_key(
            path="/bff/mobile/tasks",
            user_id=employee_id,
            role=role,
            account_type=account_type,
        )
        if settings.enable_bff_cache:
            cached = cache.get(key)
            if cached:
                return MobileTasksResponse.model_validate(cached)

        counts = db.execute(
            text(
                """
                SELECT
                    COUNT(*) AS total_tasks,
                    SUM(CASE WHEN status::text = 'ACTIVE' THEN 1 ELSE 0 END) AS active_tasks,
                    SUM(CASE WHEN status::text = 'COMPLETED' THEN 1 ELSE 0 END) AS completed_tasks,
                    SUM(CASE WHEN status::text = 'CREATED' THEN 1 ELSE 0 END) AS created_tasks,
                    SUM(CASE WHEN status::text = 'CANCELLED' THEN 1 ELSE 0 END) AS cancelled_tasks
                FROM engineer_tasks
                WHERE assigned_engineer_id = :employee_id
                """
            ),
            {"employee_id": employee_id},
        ).mappings().one()

        task_rows = db.execute(
            text(
                """
                SELECT
                    et.task_id,
                    et.request_id,
                    ur.title AS request_title,
                    et.facility_id,
                    COALESCE(sf.name, '') AS facility_name,
                    COALESCE(sf.address, '') AS facility_address,
                    et.description,
                    et.operator_comment,
                    et.status::text AS status,
                    et.created_at,
                    et.started_at,
                    et.completed_at
                FROM engineer_tasks et
                LEFT JOIN sports_facilities sf ON sf.facility_id = et.facility_id
                LEFT JOIN user_requests ur ON ur.request_id = et.request_id
                WHERE et.assigned_engineer_id = :employee_id
                ORDER BY et.created_at DESC
                """
            ),
            {"employee_id": employee_id},
        ).mappings().all()

        tasks = [
            MobileTaskItem(
                task_id=int(row["task_id"]),
                request_id=int(row["request_id"]) if row["request_id"] is not None else None,
                title=(
                    (str(row["request_title"]).strip() if row.get("request_title") is not None else "")
                    or (f"Request #{int(row['request_id'])}" if row["request_id"] is not None else None)
                ),
                request_title=(
                    str(row["request_title"]).strip()
                    if row.get("request_title") is not None and str(row["request_title"]).strip()
                    else None
                ),
                facility_id=int(row["facility_id"]),
                facility_name=str(row["facility_name"] or ""),
                facility_address=str(row["facility_address"] or ""),
                description=str(row["description"] or ""),
                operator_comment=str(row["operator_comment"]) if row["operator_comment"] is not None else None,
                status=str(row["status"] or "CREATED"),
                status_label=STATUS_LABELS.get(str(row["status"] or "CREATED"), "Created"),
                created_at=_iso(row["created_at"]) or "",
                started_at=_iso(row["started_at"]),
                completed_at=_iso(row["completed_at"]),
            )
            for row in task_rows
        ]

        total = int(counts["total_tasks"] or 0)
        active = int(counts["active_tasks"] or 0)
        completed = int(counts["completed_tasks"] or 0)
        created = int(counts["created_tasks"] or 0)
        cancelled = int(counts["cancelled_tasks"] or 0)
        response = MobileTasksResponse(
            total=total,
            active=active,
            completed=completed,
            created=created,
            cancelled=cancelled,
            summary=MobileTaskSummary(
                total=total,
                active=active,
                completed=completed,
                created=created,
                cancelled=cancelled,
            ),
            tasks=tasks,
            quick_actions=["start", "finish", "cancel"],
        )
        if settings.enable_bff_cache:
            cache.set(key, response.model_dump(), ttl_seconds=30)
        return response
