from __future__ import annotations

import logging
from datetime import datetime
from typing import Callable

from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.cache import build_cache_key, cache
from app.core.config import settings
from app.schemas.bff import DesktopReportItem, DesktopReportsResponse


def _is_desktop_privileged(roles: list[str]) -> bool:
    return bool({"OPERATOR", "CHIEF_ENGINEER"}.intersection(set(roles)))


class DesktopReportsQueryService:
    @staticmethod
    def get_desktop_reports(
        db: Session,
        *,
        principal_account_type,
        principal_roles: list[str],
        principal_subject_id: int,
        employee_id: int,
        facility_id: int | None,
        requested_engineer_id: int | None,
        source: str | None,
        created_from: datetime | None,
        created_to: datetime | None,
        page: int,
        limit: int,
        normalize_source: Callable[[str | None], str | None],
        to_desktop_report_item: Callable[[dict[str, object]], DesktopReportItem],
        logger: logging.Logger | None = None,
    ) -> DesktopReportsResponse:
        if principal_account_type.value != "EMPLOYEE":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Employee account required")
        if created_from and created_to and created_from > created_to:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="created_from must be before created_to")

        normalized_source = normalize_source(source)
        normalized_facility_id = facility_id if facility_id and facility_id > 0 else None
        normalized_engineer_id = requested_engineer_id if requested_engineer_id and requested_engineer_id > 0 else None

        privileged = _is_desktop_privileged(principal_roles)
        if not privileged and normalized_engineer_id is not None and normalized_engineer_id != employee_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Engineer can view only own reports")
        target_engineer_id = normalized_engineer_id if privileged else employee_id

        source_like_pattern = '{"source": "uploaded_file"%'
        where_clauses: list[str] = []
        params: dict[str, object] = {}

        if normalized_facility_id is not None:
            where_clauses.append("et.facility_id = :facility_id")
            params["facility_id"] = normalized_facility_id
        if target_engineer_id is not None:
            where_clauses.append("er.engineer_id = :engineer_id")
            params["engineer_id"] = target_engineer_id
        if created_from is not None:
            where_clauses.append("er.created_at >= :created_from")
            params["created_from"] = created_from
        if created_to is not None:
            where_clauses.append("er.created_at <= :created_to")
            params["created_to"] = created_to
        if normalized_source == "uploaded_file":
            where_clauses.append("er.report_text LIKE :uploaded_pattern")
            params["uploaded_pattern"] = source_like_pattern
        if normalized_source == "generated_text":
            where_clauses.append("(er.report_text IS NULL OR er.report_text NOT LIKE :uploaded_pattern)")
            params["uploaded_pattern"] = source_like_pattern

        where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
        key = build_cache_key(
            path=(
                "/bff/desktop/reports"
                f"?facility_id={normalized_facility_id}"
                f"&engineer_id={target_engineer_id}"
                f"&source={normalized_source}"
                f"&created_from={created_from.isoformat() if created_from else ''}"
                f"&created_to={created_to.isoformat() if created_to else ''}"
                f"&page={page}"
                f"&limit={limit}"
            ),
            user_id=principal_subject_id,
            role=(principal_roles[0] if principal_roles else None),
            account_type=principal_account_type.value,
        )
        if settings.enable_bff_cache:
            cached = cache.get(key)
            if cached:
                return DesktopReportsResponse.model_validate(cached)

        total_row = db.execute(
            text(
                f"""
                SELECT COUNT(*) AS total
                FROM engineer_reports er
                JOIN engineer_tasks et ON et.task_id = er.task_id
                {where_sql}
                """
            ),
            params,
        ).mappings().one()
        total = int(total_row["total"] or 0)

        offset = (page - 1) * limit
        page_params = dict(params)
        page_params["limit"] = limit
        page_params["offset"] = offset
        rows = db.execute(
            text(
                f"""
                SELECT
                    er.report_id,
                    er.task_id,
                    er.engineer_id,
                    er.report_text,
                    er.created_at,
                    et.facility_id,
                    et.status::text AS task_status,
                    COALESCE(sf.name, '') AS facility_name,
                    COALESCE(TRIM(CONCAT_WS(' ', e.last_name, e.first_name, e.middle_name)), '') AS engineer_name
                FROM engineer_reports er
                JOIN engineer_tasks et ON et.task_id = er.task_id
                LEFT JOIN sports_facilities sf ON sf.facility_id = et.facility_id
                LEFT JOIN employees e ON e.employee_id = er.engineer_id
                {where_sql}
                ORDER BY er.created_at DESC
                LIMIT :limit OFFSET :offset
                """
            ),
            page_params,
        ).mappings().all()

        items = [to_desktop_report_item(dict(row)) for row in rows]
        response = DesktopReportsResponse(total=total, page=page, limit=limit, items=items)
        if logger is not None:
            logger.info(
                "Desktop reports loaded: employee_id=%s roles=%s total=%s facility_id=%s engineer_id=%s source=%s page=%s limit=%s",
                employee_id,
                principal_roles,
                total,
                normalized_facility_id,
                target_engineer_id,
                normalized_source,
                page,
                limit,
            )
        if settings.enable_bff_cache:
            cache.set(key, response.model_dump(), ttl_seconds=20)
        return response
