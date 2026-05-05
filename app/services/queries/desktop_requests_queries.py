from __future__ import annotations

from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.pagination import resolve_pagination
from app.schemas.bff import DesktopRequestItem, DesktopRequestsPageResponse


def _iso(dt: datetime | None) -> str:
    if not dt:
        return ""
    return dt.isoformat().replace("+00:00", "Z")


def _is_desktop_privileged(roles: list[str]) -> bool:
    return bool({"OPERATOR", "CHIEF_ENGINEER"}.intersection(set(roles)))


class DesktopRequestsQueryService:
    @staticmethod
    def fetch_desktop_requests(
        db: Session,
        *,
        assigned_engineer_id: int | None = None,
        status_filter: str | None = None,
        facility_id: int | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        page: int | None = None,
        limit: int | None = None,
    ) -> tuple[list[DesktopRequestItem], int]:
        pagination = resolve_pagination(page, limit)
        sql = """
            SELECT
                ur.request_id AS id,
                ur.facility_id AS facility_id,
                ur.title AS title,
                COALESCE(sf.name, '') AS facility,
                ur.description AS description,
                ur.created_at AS created_at,
                ur.status::text AS status,
                COALESCE(TRIM(CONCAT_WS(' ', e.last_name, e.first_name, e.middle_name)), '') AS engineer
            FROM user_requests ur
            LEFT JOIN sports_facilities sf ON sf.facility_id = ur.facility_id
            LEFT JOIN engineer_tasks et ON et.request_id = ur.request_id
            LEFT JOIN employees e ON e.employee_id = et.assigned_engineer_id
        """
        count_sql = """
            SELECT COUNT(*) AS total
            FROM user_requests ur
            LEFT JOIN engineer_tasks et ON et.request_id = ur.request_id
        """
        where_parts: list[str] = []
        params: dict[str, object] = {}
        if assigned_engineer_id is not None:
            where_parts.append("et.assigned_engineer_id = :assigned_engineer_id")
            params["assigned_engineer_id"] = assigned_engineer_id
        if status_filter is not None:
            where_parts.append("ur.status::text = :status_filter")
            params["status_filter"] = status_filter
        if facility_id is not None:
            where_parts.append("ur.facility_id = :facility_id")
            params["facility_id"] = facility_id
        if date_from is not None:
            where_parts.append("ur.created_at >= :date_from")
            params["date_from"] = date_from
        if date_to is not None:
            where_parts.append("ur.created_at <= :date_to")
            params["date_to"] = date_to

        where_sql = f" WHERE {' AND '.join(where_parts)}" if where_parts else ""
        total_row = db.execute(text(count_sql + where_sql), params).mappings().one()
        total = int(total_row["total"] or 0)

        sql += where_sql
        sql += " ORDER BY ur.created_at DESC"
        if pagination is not None:
            sql += " LIMIT :limit OFFSET :offset"
            params["limit"] = pagination.limit
            params["offset"] = pagination.offset

        rows = db.execute(text(sql), params).mappings().all()

        out: list[DesktopRequestItem] = []
        for row in rows:
            request_id = int(row["id"])
            row_title = str(row["title"]).strip() if row.get("title") is not None else ""
            out.append(
                DesktopRequestItem(
                    id=request_id,
                    title=row_title or f"Request #{request_id}",
                    facility=str(row["facility"] or ""),
                    description=str(row["description"] or ""),
                    date=_iso(row.get("created_at")),
                    status=str(row["status"] or ""),
                    engineer=str(row["engineer"] or ""),
                )
            )
        return out, total

    @staticmethod
    def get_role_scoped_requests(
        db: Session,
        *,
        principal_account_type,
        principal_roles: list[str],
        employee_id: int,
        status_filter: str | None,
        facility_id: int | None,
        requested_engineer_id: int | None,
        date_from: datetime | None,
        date_to: datetime | None,
        page: int | None,
        limit: int | None,
    ) -> list[DesktopRequestItem] | DesktopRequestsPageResponse:
        if principal_account_type.value != "EMPLOYEE":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Employee account required")
        if date_from and date_to and date_from > date_to:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="date_from must be before date_to")

        pagination = resolve_pagination(page, limit)
        scoped_engineer = requested_engineer_id
        if not _is_desktop_privileged(principal_roles):
            if requested_engineer_id is not None and requested_engineer_id != employee_id:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Engineer can view only assigned requests")
            scoped_engineer = employee_id

        items, total = DesktopRequestsQueryService.fetch_desktop_requests(
            db,
            assigned_engineer_id=scoped_engineer,
            status_filter=status_filter,
            facility_id=facility_id,
            date_from=date_from,
            date_to=date_to,
            page=page,
            limit=limit,
        )
        if pagination is None:
            return items
        return DesktopRequestsPageResponse(items=items, page=pagination.page, limit=pagination.limit, total=total)
