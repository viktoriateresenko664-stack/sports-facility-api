import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import AuthPrincipal, get_current_employee, get_current_principal, require_roles
from app.core.config import settings
from app.core.cache import build_cache_key, cache
from app.core.pagination import resolve_pagination
from app.core.status_normalization import normalize_request_status
from app.db.session import get_db
from app.models.employee import Employee
from app.models.enums import AccountType
from app.models.enums import RequestStatus
from app.models.user_request import UserRequest
from app.schemas.bff import (
    DesktopAssignEngineerRequest,
    DesktopAssignEngineerResponse,
    DesktopDashboardResponse,
    DesktopEmployeeItem,
    DesktopFacilityItem,
    DesktopLogsPageResponse,
    DesktopLogItem,
    DesktopMonitoringResponse,
    DesktopReportDetailResponse,
    DesktopReportItem,
    DesktopReportsResponse,
    DesktopRequestsPageResponse,
    DesktopRequestItem,
)
from app.schemas.engineer_task import EngineerTaskCreate
from app.services.engineer_task_service import EngineerTaskService
from app.services.report_service import ReportService

router = APIRouter(prefix="/bff/desktop", tags=["bff-desktop"])
task_service = EngineerTaskService()
DESKTOP_PRIVILEGED_ROLES = {"OPERATOR", "CHIEF_ENGINEER"}
DESKTOP_EMPLOYEE_ROLES = ("OPERATOR", "CHIEF_ENGINEER")
logger = logging.getLogger(__name__)


def _iso(dt: datetime | None) -> str:
    if not dt:
        return ""
    return dt.isoformat().replace("+00:00", "Z")


def _is_desktop_privileged(principal: AuthPrincipal) -> bool:
    return bool(DESKTOP_PRIVILEGED_ROLES.intersection(set(principal.roles)))


def _require_employee_account(principal: AuthPrincipal) -> None:
    if principal.account_type != AccountType.EMPLOYEE:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Employee account required")


def _normalize_reports_source(source: str | None) -> str | None:
    if source is None:
        return None
    normalized = source.strip().lower()
    if normalized in {"", "all"}:
        return None
    if normalized in {"uploaded_file", "uploaded", "file"}:
        return "uploaded_file"
    if normalized in {"generated_text", "generated", "text"}:
        return "generated_text"
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported source filter")


def _to_desktop_report_item(row: dict[str, object]) -> DesktopReportItem:
    report_text = row.get("report_text")
    metadata = ReportService.parse_uploaded_file_metadata(report_text if isinstance(report_text, str) else None)
    source = "uploaded_file" if metadata else "generated_text"
    original_filename = None
    content_type = None
    stored_filename = None
    size_bytes = None
    has_preview = False
    if metadata:
        original_filename = metadata.get("original_filename") if isinstance(metadata.get("original_filename"), str) else None
        stored_filename = metadata.get("stored_filename") if isinstance(metadata.get("stored_filename"), str) else None
        content_type = ReportService.resolve_safe_content_type(
            filename=original_filename or stored_filename,
            fallback=metadata.get("content_type") if isinstance(metadata.get("content_type"), str) else None,
        )
        size_value = metadata.get("size_bytes")
        size_bytes = int(size_value) if isinstance(size_value, int) else None
        has_preview = ReportService.is_inline_preview_content_type(content_type)

    report_id = int(row["report_id"])
    return DesktopReportItem(
        report_id=report_id,
        task_id=int(row["task_id"]),
        facility_id=int(row["facility_id"]),
        facility_name=str(row.get("facility_name") or ""),
        engineer_id=int(row["engineer_id"]),
        engineer_name=str(row.get("engineer_name") or ""),
        task_status=str(row.get("task_status") or ""),
        source=source,
        created_at=_iso(row.get("created_at") if isinstance(row.get("created_at"), datetime) else None),
        original_filename=original_filename,
        content_type=content_type,
        size_bytes=size_bytes,
        download_url=f"/reports/{report_id}/download",
        preview_url=f"/reports/{report_id}/preview" if has_preview else None,
        has_preview=has_preview,
    )


@router.get(
    "/monitoring",
    response_model=DesktopMonitoringResponse,
    summary="Get Desktop Monitoring Data",
    description="Returns monitoring panels and summary data for the desktop client.",
)
def desktop_monitoring(
    db: Session = Depends(get_db),
    principal: AuthPrincipal = Depends(get_current_principal),
    _=Depends(require_roles("OPERATOR", "CHIEF_ENGINEER")),
) -> DesktopMonitoringResponse:
    if principal.account_type != AccountType.EMPLOYEE:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Employee account required")

    key = build_cache_key(
        path="/bff/desktop/monitoring",
        user_id=principal.subject_id,
        role=(principal.roles[0] if principal.roles else None),
        account_type=principal.account_type.value,
    )
    if settings.enable_bff_cache:
        cached = cache.get(key)
        if cached:
            return DesktopMonitoringResponse.model_validate(cached)

    stats = db.execute(
        text(
            """
            SELECT
                (SELECT COUNT(*) FROM sports_facilities) AS facilities_count,
                (SELECT COUNT(*) FROM engineer_tasks) AS tasks_count,
                (SELECT COUNT(*) FROM background_jobs WHERE status::text = 'PENDING') AS pending_jobs_count
            """
        )
    ).mappings().one()

    response = DesktopMonitoringResponse(
        summary="desktop monitoring",
        facilities_count=int(stats["facilities_count"] or 0),
        tasks_count=int(stats["tasks_count"] or 0),
        pending_jobs_count=int(stats["pending_jobs_count"] or 0),
        panels=["sensors", "equipment", "jobs"],
    )
    if settings.enable_bff_cache:
        cache.set(key, response.model_dump(), ttl_seconds=30)
    return response


@router.get(
    "/dashboard",
    response_model=DesktopDashboardResponse,
    summary="Get Desktop Dashboard",
    description="Returns facilities in the legacy desktop dashboard format.",
)
def desktop_dashboard(
    db: Session = Depends(get_db),
    principal: AuthPrincipal = Depends(require_roles(*DESKTOP_EMPLOYEE_ROLES)),
) -> DesktopDashboardResponse:
    _require_employee_account(principal)
    rows = db.execute(
        text(
            """
            SELECT
                facility_id AS id,
                name,
                facility_type AS type,
                address,
                status::text AS status,
                latitude,
                longitude
            FROM sports_facilities
            ORDER BY facility_id
            """
        )
    ).mappings().all()
    facilities = [DesktopFacilityItem.model_validate(dict(row)) for row in rows]
    return DesktopDashboardResponse(facilities=facilities)


@router.get(
    "/requests",
    response_model=list[DesktopRequestItem] | DesktopRequestsPageResponse,
    summary="Get Desktop Requests (Role Scoped)",
    description=(
        "Returns role-scoped requests: operators/chief/admin receive all requests, "
        "engineers receive only requests assigned to their tasks."
    ),
)
def desktop_requests(
    status_filter: str | None = Query(default=None, alias="status"),
    facility_id: int | None = None,
    assigned_engineer: int | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    page: int | None = Query(default=None, ge=1),
    limit: int | None = Query(default=None, ge=1),
    db: Session = Depends(get_db),
    employee: Employee = Depends(get_current_employee),
    principal: AuthPrincipal = Depends(require_roles(*DESKTOP_EMPLOYEE_ROLES)),
) -> list[DesktopRequestItem] | DesktopRequestsPageResponse:
    _require_employee_account(principal)
    if date_from and date_to and date_from > date_to:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="date_from must be before date_to")

    normalized_status = normalize_request_status(status_filter)
    if status_filter is not None and normalized_status is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported status filter")

    pagination = resolve_pagination(page, limit)
    scoped_engineer = assigned_engineer
    if _is_desktop_privileged(principal):
        pass
    else:
        if assigned_engineer is not None and assigned_engineer != employee.employee_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Engineer can view only assigned requests")
        scoped_engineer = employee.employee_id

    items, total = _fetch_desktop_requests(
        db,
        assigned_engineer_id=scoped_engineer,
        status_filter=normalized_status,
        facility_id=facility_id,
        date_from=date_from,
        date_to=date_to,
        page=page,
        limit=limit,
    )
    if pagination is None:
        return items
    return DesktopRequestsPageResponse(items=items, page=pagination.page, limit=pagination.limit, total=total)


def _fetch_desktop_requests(
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
                title=row_title or f"Заявка #{request_id}",
                facility=str(row["facility"] or ""),
                description=str(row["description"] or ""),
                date=_iso(row.get("created_at")),
                status=str(row["status"] or ""),
                engineer=str(row["engineer"] or ""),
            )
        )
    return out, total


@router.get(
    "/requests/all",
    response_model=list[DesktopRequestItem],
    summary="Get Desktop Requests (All)",
    description="Returns legacy desktop requests list format.",
)
def desktop_requests_all(
    db: Session = Depends(get_db),
    principal: AuthPrincipal = Depends(require_roles("OPERATOR", "CHIEF_ENGINEER")),
) -> list[DesktopRequestItem]:
    _require_employee_account(principal)
    items, _total = _fetch_desktop_requests(db)
    return items


@router.get(
    "/requests/my",
    response_model=list[DesktopRequestItem],
    summary="Get Desktop Requests (My)",
    description="Returns requests filtered by assigned engineer when employee JWT is present.",
)
def desktop_requests_my(
    db: Session = Depends(get_db),
    employee: Employee = Depends(get_current_employee),
    principal: AuthPrincipal = Depends(require_roles("OPERATOR", "CHIEF_ENGINEER")),
) -> list[DesktopRequestItem]:
    _require_employee_account(principal)
    items, _total = _fetch_desktop_requests(db, assigned_engineer_id=employee.employee_id)
    return items


@router.get(
    "/employees",
    response_model=list[DesktopEmployeeItem],
    summary="Get Desktop Employees",
    description="Returns legacy desktop employees list format.",
)
def desktop_employees(
    db: Session = Depends(get_db),
    _=Depends(require_roles("OPERATOR", "CHIEF_ENGINEER")),
) -> list[DesktopEmployeeItem]:
    rows = db.execute(
        text(
            """
            SELECT
                employee_id AS id,
                TRIM(CONCAT_WS(' ', last_name, first_name, middle_name)) AS name,
                COALESCE(phone, '') AS phone,
                COALESCE(email, '') AS email,
                COALESCE(position, '') AS position
            FROM employees
            ORDER BY employee_id
            """
        )
    ).mappings().all()
    return [DesktopEmployeeItem.model_validate(dict(row)) for row in rows]


@router.get(
    "/logs",
    response_model=list[DesktopLogItem] | DesktopLogsPageResponse,
    summary="Get Desktop Logs",
    description="Returns legacy desktop logs list format.",
)
def desktop_logs(
    status_filter: str | None = Query(default=None, alias="status"),
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    page: int | None = Query(default=None, ge=1),
    limit: int | None = Query(default=None, ge=1),
    db: Session = Depends(get_db),
    employee: Employee = Depends(get_current_employee),
    principal: AuthPrincipal = Depends(require_roles(*DESKTOP_EMPLOYEE_ROLES)),
) -> list[DesktopLogItem] | DesktopLogsPageResponse:
    _require_employee_account(principal)
    if date_from and date_to and date_from > date_to:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="date_from must be before date_to")
    pagination = resolve_pagination(page, limit)
    where_parts: list[str] = []
    params: dict[str, object] = {}
    if not _is_desktop_privileged(principal):
        where_parts.append("l.actor_employee_id = :actor_employee_id")
        params["actor_employee_id"] = employee.employee_id
    if status_filter is not None:
        normalized = status_filter.strip().upper()
        if normalized not in {"SUCCESS", "FAILED"}:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported status filter")
        where_parts.append("l.status::text = :status_filter")
        params["status_filter"] = normalized
    if date_from is not None:
        where_parts.append("l.created_at >= :date_from")
        params["date_from"] = date_from
    if date_to is not None:
        where_parts.append("l.created_at <= :date_to")
        params["date_to"] = date_to
    where_sql = f"WHERE {' AND '.join(where_parts)}" if where_parts else ""

    total_row = db.execute(
        text(
            f"""
            SELECT COUNT(*) AS total
            FROM system_action_log l
            {where_sql}
            """
        ),
        params,
    ).mappings().one()
    total = int(total_row["total"] or 0)

    row_params = dict(params)
    if pagination is not None:
        row_params["limit"] = pagination.limit
        row_params["offset"] = pagination.offset

    rows = db.execute(
        text(
            f"""
            SELECT
                l.log_id AS id,
                COALESCE(
                    u.username,
                    TRIM(CONCAT_WS(' ', e.last_name, e.first_name, e.middle_name)),
                    ''
                ) AS "user",
                COALESCE(l.user_role, '') AS role,
                COALESCE(l.action_type, '') AS action,
                COALESCE(l.entity_type, '') AS "object",
                l.created_at AS created_at,
                l.status::text AS status
            FROM system_action_log l
            LEFT JOIN users u ON u.user_id = l.actor_user_id
            LEFT JOIN employees e ON e.employee_id = l.actor_employee_id
            {where_sql}
            ORDER BY l.created_at DESC
            """
            + (" LIMIT :limit OFFSET :offset" if pagination is not None else " LIMIT 1000")
        ),
        row_params,
    ).mappings().all()
    out: list[DesktopLogItem] = []
    for row in rows:
        out.append(
            DesktopLogItem(
                id=int(row["id"]),
                user=str(row["user"] or ""),
                role=str(row["role"] or ""),
                action=str(row["action"] or ""),
                object=str(row["object"] or ""),
                date=_iso(row.get("created_at")),
                status=str(row["status"] or ""),
            )
        )
    if pagination is None:
        return out
    return DesktopLogsPageResponse(items=out, page=pagination.page, limit=pagination.limit, total=total)


@router.get(
    "/reports",
    response_model=DesktopReportsResponse,
    summary="Get Desktop Reports Registry",
    description="Returns paginated report registry for desktop with filtering by facility, engineer, source and date.",
)
def desktop_reports(
    facility_id: int | None = None,
    engineer_id: int | None = None,
    source: str | None = None,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    employee: Employee = Depends(get_current_employee),
    principal: AuthPrincipal = Depends(require_roles("OPERATOR", "CHIEF_ENGINEER")),
) -> DesktopReportsResponse:
    if principal.account_type != AccountType.EMPLOYEE:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Employee account required")

    if created_from and created_to and created_from > created_to:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="created_from must be before created_to")

    normalized_source = _normalize_reports_source(source)
    normalized_facility_id = facility_id if facility_id and facility_id > 0 else None
    normalized_engineer_id = engineer_id if engineer_id and engineer_id > 0 else None

    privileged = _is_desktop_privileged(principal)
    if not privileged and normalized_engineer_id is not None and normalized_engineer_id != employee.employee_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Engineer can view only own reports")
    target_engineer_id = normalized_engineer_id if privileged else employee.employee_id

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
        user_id=principal.subject_id,
        role=(principal.roles[0] if principal.roles else None),
        account_type=principal.account_type.value,
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

    items = [_to_desktop_report_item(dict(row)) for row in rows]
    response = DesktopReportsResponse(total=total, page=page, limit=limit, items=items)
    logger.info(
        "Desktop reports loaded: employee_id=%s roles=%s total=%s facility_id=%s engineer_id=%s source=%s page=%s limit=%s",
        employee.employee_id,
        principal.roles,
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


@router.get(
    "/reports/{report_id}",
    response_model=DesktopReportDetailResponse,
    summary="Get Desktop Report Detail",
    description="Returns detailed report card for desktop including links for preview/download.",
)
def desktop_report_detail(
    report_id: int,
    db: Session = Depends(get_db),
    employee: Employee = Depends(get_current_employee),
    principal: AuthPrincipal = Depends(require_roles("OPERATOR", "CHIEF_ENGINEER")),
) -> DesktopReportDetailResponse:
    if principal.account_type != AccountType.EMPLOYEE:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Employee account required")

    row = db.execute(
        text(
            """
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
            WHERE er.report_id = :report_id
            """
        ),
        {"report_id": report_id},
    ).mappings().first()

    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")
    if not _is_desktop_privileged(principal) and int(row["engineer_id"]) != employee.employee_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")

    report_text = row.get("report_text")
    metadata = ReportService.parse_uploaded_file_metadata(report_text if isinstance(report_text, str) else None)
    source = "uploaded_file" if metadata else "generated_text"
    original_filename = None
    content_type = None
    size_bytes = None
    stored_relative_path = None
    stored_filename = None
    has_preview = False
    if metadata:
        original_filename = metadata.get("original_filename") if isinstance(metadata.get("original_filename"), str) else None
        stored_filename = metadata.get("stored_filename") if isinstance(metadata.get("stored_filename"), str) else None
        content_type = ReportService.resolve_safe_content_type(
            filename=original_filename or stored_filename,
            fallback=metadata.get("content_type") if isinstance(metadata.get("content_type"), str) else None,
        )
        stored_relative_path = (
            metadata.get("stored_relative_path")
            if isinstance(metadata.get("stored_relative_path"), str)
            else None
        )
        size_value = metadata.get("size_bytes")
        size_bytes = int(size_value) if isinstance(size_value, int) else None
        has_preview = ReportService.is_inline_preview_content_type(content_type)

    return DesktopReportDetailResponse(
        report_id=int(row["report_id"]),
        task_id=int(row["task_id"]),
        facility_id=int(row["facility_id"]),
        facility_name=str(row.get("facility_name") or ""),
        engineer_id=int(row["engineer_id"]),
        engineer_name=str(row.get("engineer_name") or ""),
        task_status=str(row.get("task_status") or ""),
        source=source,
        created_at=_iso(row.get("created_at") if isinstance(row.get("created_at"), datetime) else None),
        report_text=str(report_text) if source == "generated_text" and isinstance(report_text, str) else None,
        original_filename=original_filename,
        content_type=content_type,
        size_bytes=size_bytes,
        stored_relative_path=stored_relative_path,
        download_url=f"/reports/{int(row['report_id'])}/download",
        preview_url=f"/reports/{int(row['report_id'])}/preview" if has_preview else None,
        has_preview=has_preview,
    )


@router.post(
    "/requests/{request_id}/assign",
    response_model=DesktopAssignEngineerResponse,
    summary="Assign Engineer To Request",
    description="Creates engineer task for a user request and returns assignment result.",
)
def desktop_assign_engineer(
    request_id: int,
    payload: DesktopAssignEngineerRequest,
    db: Session = Depends(get_db),
    principal: AuthPrincipal = Depends(get_current_principal),
    _=Depends(require_roles("OPERATOR", "CHIEF_ENGINEER")),
) -> DesktopAssignEngineerResponse:
    if principal.account_type != AccountType.EMPLOYEE:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Employee account required")

    request_obj = db.get(UserRequest, request_id)
    if not request_obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")

    engineer = db.get(Employee, payload.assigned_engineer_id)
    if not engineer or not engineer.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assigned engineer not found")

    existing = db.execute(
        text("SELECT task_id FROM engineer_tasks WHERE request_id = :request_id"),
        {"request_id": request_id},
    ).mappings().first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Task already exists for this request")

    task_payload = EngineerTaskCreate(
        facility_id=request_obj.facility_id,
        request_id=request_obj.request_id,
        assigned_engineer_id=payload.assigned_engineer_id,
        description=request_obj.description,
        operator_comment=payload.operator_comment,
    )
    task, job_id = task_service.create_task_with_background_job(db, task_payload, principal.subject_id)

    if request_obj.status == RequestStatus.CREATED:
        request_obj.status = RequestStatus.ASSIGNED
        db.add(request_obj)
        db.commit()
    if settings.enable_bff_cache:
        cache.invalidate(prefix="/bff/")

    return DesktopAssignEngineerResponse(
        request_id=request_id,
        task_id=task.task_id,
        assigned_engineer_id=task.assigned_engineer_id,
        job_id=job_id,
        status=task.status.value if hasattr(task.status, "value") else str(task.status),
    )
