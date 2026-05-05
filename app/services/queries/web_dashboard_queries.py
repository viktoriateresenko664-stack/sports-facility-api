from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.cache import build_cache_key, cache
from app.core.config import settings
from app.schemas.bff import WebDashboardResponse


class WebDashboardQueryService:
    @staticmethod
    def get_dashboard(db: Session, *, user_id: int) -> WebDashboardResponse:
        key = build_cache_key(path="/bff/web/dashboard", user_id=user_id, role="USER", account_type="USER")
        if settings.enable_bff_cache:
            cached = cache.get(key)
            if cached:
                return WebDashboardResponse.model_validate(cached)

        counts = db.execute(
            text(
                """
                SELECT
                    COUNT(*) AS total_tasks,
                    SUM(CASE WHEN status::text = 'ACTIVE' THEN 1 ELSE 0 END) AS active_tasks,
                    SUM(CASE WHEN status::text = 'COMPLETED' THEN 1 ELSE 0 END) AS completed_tasks
                FROM engineer_tasks
                """
            )
        ).mappings().one()

        response = WebDashboardResponse(
            summary="web dashboard",
            widgets=["facilities", "active_tasks", "alerts"],
            total_tasks=int(counts["total_tasks"] or 0),
            active_tasks=int(counts["active_tasks"] or 0),
            completed_tasks=int(counts["completed_tasks"] or 0),
        )
        if settings.enable_bff_cache:
            cache.set(key, response.model_dump(), ttl_seconds=30)
        return response
