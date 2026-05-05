import logging
from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Header, Query, UploadFile, status
from fastapi.responses import FileResponse, Response
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import AuthPrincipal, get_current_employee, require_roles
from app.core.cache import cache
from app.core.pagination import resolve_pagination
from app.core.sanitizer import sanitize_text
from app.core.status_normalization import normalize_task_status
from app.db.session import get_db
from app.models.employee import Employee
from app.models.engineer_report import EngineerReport
from app.models.engineer_task import EngineerTask
from app.models.enums import AccountType, LogStatus, TaskStatus
from app.schemas.background_job import BackgroundJobResponse
from app.schemas.background_job import ReportJobStatusResponse
from app.schemas.engineer_report import (
    EngineerReportFileResponse,
    EngineerReportsPageResponse,
    GenerateReportDelayedRequest,
    GenerateReportRequest,
    SeedReportsRequest,
    SeedReportsResponse,
)
from app.services.background_job_service import BackgroundJobService
from app.services.domain_event_service import DomainEventService
from app.services.incident_recovery_service import incident_recovery_service
from app.services.log_service import LogService
from app.services.report_service import ReportService
from app.services.task_stream_service import task_stream_service
from app.tasks.report_tasks import generate_engineer_report_task

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/reports", tags=["reports"])
job_service = BackgroundJobService()
PRIVILEGED_ROLES = {"OPERATOR", "CHIEF_ENGINEER"}
REPORT_RESPONSES = {
    400: {"description": "Bad Request"},
    401: {"description": "Unauthorized"},
    403: {"description": "Forbidden"},
    404: {"description": "Not Found"},
    409: {"description": "Conflict"},
    413: {"description": "Payload Too Large"},
}


def _is_privileged(principal: AuthPrincipal) -> bool:
    return bool(PRIVILEGED_ROLES.intersection(set(principal.roles)))


def _get_accessible_task_or_404(
    db: Session,
    task_id: int,
    employee: Employee,
    principal: AuthPrincipal,
    lock_for_update: bool = False,
) -> EngineerTask:
    query = db.query(EngineerTask).filter(EngineerTask.task_id == task_id)
    if lock_for_update:
        query = query.with_for_update()
    task = query.first()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    if not _is_privileged(principal) and task.assigned_engineer_id != employee.employee_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return task


def _to_report_file_response(report: EngineerReport) -> EngineerReportFileResponse:
    metadata = ReportService.parse_uploaded_file_metadata(report.report_text)
    if not metadata:
        return EngineerReportFileResponse(
            report_id=report.report_id,
            task_id=report.task_id,
            engineer_id=report.engineer_id,
            source="generated_text",
            created_at=report.created_at,
            report_text=report.report_text,
        )

    original_filename = metadata.get("original_filename")
    content_type = metadata.get("content_type")
    stored_filename = metadata.get("stored_filename")
    safe_content_type = ReportService.resolve_safe_content_type(
        filename=(
            original_filename
            if isinstance(original_filename, str)
            else (stored_filename if isinstance(stored_filename, str) else None)
        ),
        fallback=content_type if isinstance(content_type, str) else None,
    )
    size_bytes = metadata.get("size_bytes")
    return EngineerReportFileResponse(
        report_id=report.report_id,
        task_id=report.task_id,
        engineer_id=report.engineer_id,
        source="uploaded_file",
        created_at=report.created_at,
        original_filename=original_filename if isinstance(original_filename, str) else None,
        content_type=safe_content_type,
        size_bytes=int(size_bytes) if isinstance(size_bytes, int) else None,
        download_url=f"/reports/{report.report_id}/download",
    )


_REPORT_JOB_STATUS_MAP = {
    "PENDING": "CREATED",
    "PROCESSING": "ACTIVE",
    "SUCCESS": "COMPLETED",
    "FAILED": "CANCELLED",
}


def _to_report_job_status_response(job) -> ReportJobStatusResponse:  # type: ignore[no-untyped-def]
    raw_status = str(getattr(job, "status", "") or "").upper()
    mapped_status = _REPORT_JOB_STATUS_MAP.get(raw_status, "CREATED")
    report_id = None
    result = getattr(job, "result", None)
    if isinstance(result, dict):
        result_report_id = result.get("report_id")
        if isinstance(result_report_id, int):
            report_id = result_report_id
        elif isinstance(result_report_id, str) and result_report_id.isdigit():
            report_id = int(result_report_id)
    error_text = getattr(job, "error", None)
    return ReportJobStatusResponse(
        job_id=str(job.job_id),
        status=mapped_status,
        report_id=report_id,
        error=str(error_text) if isinstance(error_text, str) and error_text.strip() else None,
    )


def _assert_job_access(principal: AuthPrincipal, job) -> None:  # type: ignore[no-untyped-def]
    is_admin = "ADMIN" in principal.roles
    if is_admin:
        return
    if principal.account_type == AccountType.USER:
        if not (job.owner_type == AccountType.USER and job.owner_id == principal.subject_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
        return
    if principal.account_type == AccountType.EMPLOYEE:
        if not (job.owner_type == AccountType.EMPLOYEE and job.owner_id == principal.subject_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")


@router.get(
    "/template",
    responses=REPORT_RESPONSES,
    summary="Download Engineer Report Template",
    description="Returns a file template that can be used to fill and upload engineer reports.",
)
def download_report_template(
    employee: Employee = Depends(get_current_employee),
    _principal: AuthPrincipal = Depends(require_roles("ENGINEER")),
) -> FileResponse:
    _ = employee
    template_path = ReportService.ensure_template_exists()
    media_type = ReportService.template_media_type(template_path)
    return FileResponse(
        path=str(template_path),
        media_type=media_type,
        filename=template_path.name,
    )


@router.post(
    "/upload",
    response_model=EngineerReportFileResponse,
    responses=REPORT_RESPONSES,
    summary="Upload Engineer Report File",
    description=(
        "Uploads a completed report file for a task and stores it in backend report storage. "
        "Supports duplicate protection by Idempotency-Key header and file content hash."
    ),
)
def upload_report_file(
    task_id: int = Form(...),
    notes: str | None = Form(default=None, max_length=4000),
    report_file: UploadFile = File(...),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    db: Session = Depends(get_db),
    employee: Employee = Depends(get_current_employee),
    principal: AuthPrincipal = Depends(require_roles("ENGINEER")),
) -> EngineerReportFileResponse:
    normalized_key = (idempotency_key or "").strip() or None
    if normalized_key and len(normalized_key) > 128:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Idempotency-Key is too long (max 128)")

    task = _get_accessible_task_or_404(db, task_id, employee, principal, lock_for_update=True)
    existing_report = (
        db.query(EngineerReport)
        .filter(EngineerReport.task_id == task.task_id)
        .with_for_update()
        .first()
    )
    existing_metadata = (
        ReportService.parse_uploaded_file_metadata(existing_report.report_text)
        if existing_report is not None
        else None
    )
    existing_key = (
        str(existing_metadata.get("idempotency_key")).strip()
        if existing_metadata and existing_metadata.get("idempotency_key")
        else None
    )

    if normalized_key and existing_report is not None and existing_key == normalized_key:
        LogService.log_action(
            db,
            actor_employee_id=employee.employee_id,
            user_role="ENGINEER",
            action_type="UPLOAD_REPORT_FILE_DUPLICATE",
            entity_type="engineer_reports",
            entity_id=str(existing_report.report_id),
            status=LogStatus.SUCCESS,
            details={
                "task_id": task.task_id,
                "deduplicated_by": "idempotency_key",
                "idempotency_key": normalized_key,
            },
        )
        db.commit()
        logger.info(
            "Duplicate upload ignored by idempotency key: task_id=%s report_id=%s",
            task.task_id,
            existing_report.report_id,
        )
        return _to_report_file_response(existing_report)

    metadata = ReportService.save_uploaded_file(task.task_id, report_file)
    if existing_metadata and ReportService.metadata_represents_same_file(existing_metadata, metadata):
        ReportService.delete_stored_file_by_metadata(metadata)
        if existing_report is not None:
            LogService.log_action(
                db,
                actor_employee_id=employee.employee_id,
                user_role="ENGINEER",
                action_type="UPLOAD_REPORT_FILE_DUPLICATE",
                entity_type="engineer_reports",
                entity_id=str(existing_report.report_id),
                status=LogStatus.SUCCESS,
                details={
                    "task_id": task.task_id,
                    "deduplicated_by": "content_hash",
                    "idempotency_key": normalized_key,
                },
            )
            db.commit()
            logger.info(
                "Duplicate upload ignored by hash: task_id=%s report_id=%s",
                task.task_id,
                existing_report.report_id,
            )
            return _to_report_file_response(existing_report)

    report_text = ReportService.metadata_to_text(
        metadata=metadata,
        uploaded_by_engineer_id=employee.employee_id,
        notes=notes,
        idempotency_key=normalized_key,
    )
    previous_metadata = existing_metadata
    recovery_stats: dict[str, int] | None = None
    try:
        report = ReportService.upsert_report_text(
            db,
            task_id=task.task_id,
            engineer_id=task.assigned_engineer_id,
            report_text=report_text,
            commit=False,
        )
        recovery_stats = incident_recovery_service.normalize_facility_sensors(
            db,
            facility_id=task.facility_id,
            source="report_uploaded",
            task_id=task.task_id,
        )
        LogService.log_action(
            db,
            actor_employee_id=employee.employee_id,
            user_role="ENGINEER",
            action_type="UPLOAD_REPORT_FILE",
            entity_type="engineer_reports",
            entity_id=str(report.report_id),
            status=LogStatus.SUCCESS,
            details={
                "task_id": task.task_id,
                "stored_relative_path": metadata.get("stored_relative_path"),
                "size_bytes": metadata.get("size_bytes"),
                "sha256": metadata.get("sha256"),
                "idempotency_key": normalized_key,
                "sensor_recovery": recovery_stats,
            },
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        ReportService.delete_stored_file_by_metadata(metadata)
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Report already exists for this task") from exc
    except Exception:
        db.rollback()
        ReportService.delete_stored_file_by_metadata(metadata)
        raise

    if previous_metadata and not ReportService.metadata_represents_same_file(previous_metadata, metadata):
        ReportService.delete_stored_file_by_metadata(previous_metadata)

    cache.invalidate(prefix="/bff/")
    task_stream_service.publish_event(
        "REPORT_READY",
        {
            "report_id": report.report_id,
            "task_id": report.task_id,
            "engineer_id": report.engineer_id,
            "source": "uploaded_file",
        },
    )
    logger.info("Report file uploaded: task_id=%s report_id=%s", task.task_id, report.report_id)
    return _to_report_file_response(report)


@router.get(
    "/my",
    response_model=list[EngineerReportFileResponse] | EngineerReportsPageResponse,
    responses=REPORT_RESPONSES,
    summary="List Engineer Reports",
    description="Lists report entries. Engineers receive own task reports, privileged roles can request by engineer id.",
)
def list_reports(
    engineer_id: int | None = None,
    assigned_engineer: int | None = None,
    assigned_engineer_id: int | None = Query(default=None, alias="assigned_engineer_id"),
    status_filter: str | None = Query(default=None, alias="status"),
    facility_id: int | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    page: int | None = Query(default=None, ge=1),
    limit: int | None = Query(default=None, ge=1),
    db: Session = Depends(get_db),
    employee: Employee = Depends(get_current_employee),
    principal: AuthPrincipal = Depends(require_roles("ENGINEER", "OPERATOR", "CHIEF_ENGINEER")),
) -> list[EngineerReportFileResponse] | EngineerReportsPageResponse:
    if date_from and date_to and date_from > date_to:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="date_from must be before date_to")

    normalized_status = normalize_task_status(status_filter)
    if status_filter is not None and normalized_status is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported status filter")

    if assigned_engineer is not None and assigned_engineer_id is not None and assigned_engineer != assigned_engineer_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="assigned_engineer and assigned_engineer_id must match when both are provided",
        )
    requested_assigned_engineer = (
        assigned_engineer_id if assigned_engineer_id is not None else assigned_engineer
    )

    query = db.query(EngineerReport).join(EngineerTask, EngineerTask.task_id == EngineerReport.task_id)
    pagination = resolve_pagination(page, limit)

    requested_engineer = requested_assigned_engineer if requested_assigned_engineer is not None else engineer_id

    if _is_privileged(principal):
        if requested_engineer is not None:
            query = query.filter(EngineerTask.assigned_engineer_id == requested_engineer)
    else:
        if requested_engineer is not None and requested_engineer != employee.employee_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Engineer can view only own reports")
        query = query.filter(EngineerTask.assigned_engineer_id == employee.employee_id)

    if facility_id is not None:
        query = query.filter(EngineerTask.facility_id == facility_id)
    if normalized_status is not None:
        query = query.filter(EngineerTask.status == TaskStatus(normalized_status))
    if date_from is not None:
        query = query.filter(EngineerReport.created_at >= date_from)
    if date_to is not None:
        query = query.filter(EngineerReport.created_at <= date_to)

    query = query.order_by(EngineerReport.created_at.desc())
    if pagination is None:
        reports = query.all()
        return [_to_report_file_response(report) for report in reports]

    total = query.count()
    reports = query.offset(pagination.offset).limit(pagination.limit).all()
    return EngineerReportsPageResponse(
        items=[_to_report_file_response(report) for report in reports],
        page=pagination.page,
        limit=pagination.limit,
        total=total,
    )


@router.get(
    "/{report_id}/download",
    responses=REPORT_RESPONSES,
    summary="Download Uploaded Engineer Report File",
    description="Downloads the original report file if the report was uploaded as a file attachment.",
)
def download_uploaded_report_file(
    report_id: int,
    db: Session = Depends(get_db),
    employee: Employee = Depends(get_current_employee),
    principal: AuthPrincipal = Depends(require_roles("ENGINEER", "OPERATOR", "CHIEF_ENGINEER")),
) -> Response:
    report = db.get(EngineerReport, report_id)
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")

    _get_accessible_task_or_404(db, report.task_id, employee, principal)

    metadata = ReportService.parse_uploaded_file_metadata(report.report_text)
    file_path = ReportService.resolve_stored_file_path(report)
    if file_path is None:
        if metadata is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Uploaded report file is missing in storage",
            )
        generated_text = report.report_text if isinstance(report.report_text, str) else ""
        if not generated_text.strip():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Report has no downloadable content",
            )
        fallback_filename = f"report_{report.report_id}_task_{report.task_id}.txt"
        LogService.log_action(
            db,
            actor_employee_id=employee.employee_id,
            user_role="ENGINEER",
            action_type="DOWNLOAD_REPORT_TEXT",
            entity_type="engineer_reports",
            entity_id=str(report.report_id),
            status=LogStatus.SUCCESS,
            details={"task_id": report.task_id},
        )
        db.commit()
        return Response(
            content=generated_text,
            media_type="text/plain; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{fallback_filename}"'},
        )

    metadata = metadata or {}
    download_name = metadata.get("original_filename")
    stored_filename = metadata.get("stored_filename")
    content_type = ReportService.resolve_safe_content_type(
        filename=(
            download_name
            if isinstance(download_name, str)
            else (stored_filename if isinstance(stored_filename, str) else None)
        ),
        fallback=metadata.get("content_type") if isinstance(metadata.get("content_type"), str) else None,
    )
    LogService.log_action(
        db,
        actor_employee_id=employee.employee_id,
        user_role="ENGINEER",
        action_type="DOWNLOAD_REPORT_FILE",
        entity_type="engineer_reports",
        entity_id=str(report.report_id),
        status=LogStatus.SUCCESS,
        details={"task_id": report.task_id},
    )
    db.commit()
    return FileResponse(
        path=str(file_path),
        filename=download_name if isinstance(download_name, str) else file_path.name,
        media_type=content_type,
    )


@router.get(
    "/{report_id}/preview",
    responses=REPORT_RESPONSES,
    summary="Preview Uploaded Engineer Report File",
    description="Returns uploaded report file in inline mode for desktop/web preview.",
)
def preview_uploaded_report_file(
    report_id: int,
    db: Session = Depends(get_db),
    employee: Employee = Depends(get_current_employee),
    principal: AuthPrincipal = Depends(require_roles("ENGINEER", "CHIEF_ENGINEER", "OPERATOR")),
) -> Response:
    report = db.get(EngineerReport, report_id)
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")

    _get_accessible_task_or_404(db, report.task_id, employee, principal)

    metadata = ReportService.parse_uploaded_file_metadata(report.report_text)
    file_path = ReportService.resolve_stored_file_path(report)
    if file_path is None:
        if metadata is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Uploaded report file is missing in storage",
            )
        generated_text = report.report_text if isinstance(report.report_text, str) else ""
        if not generated_text.strip():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Report has no preview content",
            )
        fallback_filename = f"report_{report.report_id}_task_{report.task_id}.txt"
        LogService.log_action(
            db,
            actor_employee_id=employee.employee_id,
            user_role="ENGINEER",
            action_type="PREVIEW_REPORT_TEXT",
            entity_type="engineer_reports",
            entity_id=str(report.report_id),
            status=LogStatus.SUCCESS,
            details={"task_id": report.task_id},
        )
        db.commit()
        return Response(
            content=generated_text,
            media_type="text/plain; charset=utf-8",
            headers={"Content-Disposition": f'inline; filename="{fallback_filename}"'},
        )

    metadata = metadata or {}
    preview_name = metadata.get("original_filename")
    stored_filename = metadata.get("stored_filename")
    content_type = ReportService.resolve_safe_content_type(
        filename=(
            preview_name
            if isinstance(preview_name, str)
            else (stored_filename if isinstance(stored_filename, str) else None)
        ),
        fallback=metadata.get("content_type") if isinstance(metadata.get("content_type"), str) else None,
    )
    if not ReportService.is_inline_preview_content_type(content_type):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Report file type is not supported for inline preview",
        )
    LogService.log_action(
        db,
        actor_employee_id=employee.employee_id,
        user_role="ENGINEER",
        action_type="PREVIEW_REPORT_FILE",
        entity_type="engineer_reports",
        entity_id=str(report.report_id),
        status=LogStatus.SUCCESS,
        details={"task_id": report.task_id},
    )
    db.commit()
    return FileResponse(
        path=str(file_path),
        filename=preview_name if isinstance(preview_name, str) else file_path.name,
        media_type=content_type,
        content_disposition_type="inline",
    )


@router.get(
    "/jobs/{job_id}",
    response_model=ReportJobStatusResponse,
    responses=REPORT_RESPONSES,
    summary="Get Report Generation Job Status",
    description="Returns report generation job status in report workflow format.",
)
def get_report_job_status(
    job_id: UUID,
    db: Session = Depends(get_db),
    principal: AuthPrincipal = Depends(require_roles("ENGINEER", "OPERATOR", "CHIEF_ENGINEER", "ADMIN", "USER")),
) -> ReportJobStatusResponse:
    job = job_service.get_job(db, job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    _assert_job_access(principal, job)
    return _to_report_job_status_response(job)


@router.post(
    "/seed-samples",
    response_model=SeedReportsResponse,
    responses=REPORT_RESPONSES,
    summary="Seed Sample Reports",
    description="Creates or updates sample report files for selected tasks to speed up mobile integration testing.",
)
def seed_sample_reports(
    payload: SeedReportsRequest,
    db: Session = Depends(get_db),
    employee: Employee = Depends(get_current_employee),
    principal: AuthPrincipal = Depends(require_roles("ENGINEER")),
) -> SeedReportsResponse:
    tasks_query = db.query(EngineerTask)
    if payload.task_ids:
        tasks_query = tasks_query.filter(EngineerTask.task_id.in_(payload.task_ids))
    if not _is_privileged(principal):
        tasks_query = tasks_query.filter(EngineerTask.assigned_engineer_id == employee.employee_id)

    tasks = tasks_query.order_by(EngineerTask.task_id.desc()).all()
    if not tasks:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No accessible tasks found for report seeding")

    existing_reports = (
        db.query(EngineerReport)
        .filter(EngineerReport.task_id.in_([task.task_id for task in tasks]))
        .all()
    )
    existing_by_task_id = {row.task_id: row for row in existing_reports}

    created_count = 0
    updated_count = 0
    skipped_count = 0
    report_ids: list[int] = []

    for task in tasks:
        existing = existing_by_task_id.get(task.task_id)
        if existing and not payload.overwrite_existing:
            skipped_count += 1
            report_ids.append(existing.report_id)
            continue

        sample_text = (
            "Sample engineer report\n"
            f"Task ID: {task.task_id}\n"
            f"Facility ID: {task.facility_id}\n"
            f"Assigned engineer ID: {task.assigned_engineer_id}\n"
            f"Generated at (UTC): {datetime.now(UTC).isoformat()}\n"
            "Summary: This is a sample report generated for mobile frontend integration.\n"
        )
        metadata = ReportService.save_sample_text_file(
            task_id=task.task_id,
            report_text=sample_text,
            original_filename=f"sample_report_task_{task.task_id}.txt",
        )
        report_text = ReportService.metadata_to_text(
            metadata=metadata,
            uploaded_by_engineer_id=task.assigned_engineer_id,
            notes="Seeded sample report",
        )
        report = ReportService.upsert_report_text(
            db,
            task_id=task.task_id,
            engineer_id=task.assigned_engineer_id,
            report_text=report_text,
            commit=False,
        )
        if existing:
            updated_count += 1
        else:
            created_count += 1
        report_ids.append(report.report_id)

    LogService.log_action(
        db,
        actor_employee_id=employee.employee_id,
        user_role="ENGINEER",
        action_type="SEED_SAMPLE_REPORTS",
        entity_type="engineer_reports",
        entity_id="bulk",
        status=LogStatus.SUCCESS,
        details={
            "created_count": created_count,
            "updated_count": updated_count,
            "skipped_count": skipped_count,
            "task_ids": [task.task_id for task in tasks],
        },
    )
    db.commit()
    cache.invalidate(prefix="/bff/")

    return SeedReportsResponse(
        created_count=created_count,
        updated_count=updated_count,
        skipped_count=skipped_count,
        report_ids=report_ids,
    )


@router.post(
    "/generate",
    response_model=BackgroundJobResponse,
    responses=REPORT_RESPONSES,
    summary="Generate Engineer Report",
    description="Creates and enqueues a background job for engineer report generation.",
)
def generate_report(
    payload: GenerateReportRequest,
    db: Session = Depends(get_db),
    employee: Employee = Depends(get_current_employee),
    _principal: AuthPrincipal = Depends(require_roles("ENGINEER")),
) -> BackgroundJobResponse:
    _get_accessible_task_or_404(db, payload.task_id, employee, _principal)
    job = job_service.create_job(
        db,
        owner_id=employee.employee_id,
        owner_type=AccountType.EMPLOYEE,
        task_id=payload.task_id,
        task_name="generate_engineer_report",
        payload={
            "task_id": payload.task_id,
            "report_type": sanitize_text(payload.report_type),
            "notes": sanitize_text(payload.notes),
        },
    )
    LogService.log_action(
        db,
        actor_employee_id=employee.employee_id,
        user_role="ENGINEER",
        action_type="ENQUEUE_REPORT_JOB",
        entity_type="background_jobs",
        entity_id=str(job.job_id),
        status=LogStatus.SUCCESS,
        details={"task_id": payload.task_id},
    )
    db.commit()
    db.refresh(job)
    event = DomainEventService.publish(
        db,
        event_type="REPORT_GENERATION_REQUESTED",
        aggregate_type="background_jobs",
        aggregate_id=str(job.job_id),
        payload={"task_id": payload.task_id},
    )
    db.commit()
    DomainEventService.enqueue(str(event.event_id))
    cache.invalidate(prefix="/bff/")

    try:
        generate_engineer_report_task.apply_async(
            args=[
                str(job.job_id),
                payload.task_id,
                employee.employee_id,
                sanitize_text(payload.notes),
                sanitize_text(payload.report_type),
            ],
            ignore_result=True,
        )
        logger.info("Report job enqueued: job_id=%s", job.job_id)
    except Exception as exc:  # noqa: BLE001
        job_service.mark_failed(db, job, f"Queue enqueue failed: {exc}")
        LogService.log_action(
            db,
            actor_employee_id=employee.employee_id,
            user_role="ENGINEER",
            action_type="ENQUEUE_REPORT_JOB",
            entity_type="background_jobs",
            entity_id=str(job.job_id),
            status=LogStatus.FAILED,
            details={"task_id": payload.task_id, "error": str(exc)},
        )
        db.commit()
        db.refresh(job)
        logger.exception("Report job enqueue failed: job_id=%s", job.job_id)
    return BackgroundJobResponse.model_validate(job)


@router.post(
    "/generate-delayed",
    response_model=BackgroundJobResponse,
    responses=REPORT_RESPONSES,
    summary="Generate Engineer Report (Delayed)",
    description="Creates and enqueues a delayed background job for engineer report generation.",
)
def generate_report_delayed(
    payload: GenerateReportDelayedRequest,
    db: Session = Depends(get_db),
    employee: Employee = Depends(get_current_employee),
    _principal: AuthPrincipal = Depends(require_roles("ENGINEER")),
) -> BackgroundJobResponse:
    _get_accessible_task_or_404(db, payload.task_id, employee, _principal)
    job = job_service.create_job(
        db,
        owner_id=employee.employee_id,
        owner_type=AccountType.EMPLOYEE,
        task_id=payload.task_id,
        task_name="generate_engineer_report_delayed",
        payload={
            "task_id": payload.task_id,
            "report_type": sanitize_text(payload.report_type),
            "notes": sanitize_text(payload.notes),
            "delay_seconds": payload.delay_seconds,
        },
    )
    LogService.log_action(
        db,
        actor_employee_id=employee.employee_id,
        user_role="ENGINEER",
        action_type="ENQUEUE_REPORT_JOB_DELAYED",
        entity_type="background_jobs",
        entity_id=str(job.job_id),
        status=LogStatus.SUCCESS,
        details={"task_id": payload.task_id, "delay_seconds": payload.delay_seconds},
    )
    db.commit()
    db.refresh(job)
    event = DomainEventService.publish(
        db,
        event_type="REPORT_GENERATION_DELAYED_REQUESTED",
        aggregate_type="background_jobs",
        aggregate_id=str(job.job_id),
        payload={"task_id": payload.task_id, "delay_seconds": payload.delay_seconds},
    )
    db.commit()
    DomainEventService.enqueue(str(event.event_id))
    cache.invalidate(prefix="/bff/")

    try:
        generate_engineer_report_task.apply_async(
            args=[
                str(job.job_id),
                payload.task_id,
                employee.employee_id,
                sanitize_text(payload.notes),
                sanitize_text(payload.report_type),
            ],
            countdown=payload.delay_seconds,
            ignore_result=True,
        )
        logger.info(
            "Delayed report job enqueued: job_id=%s delay_seconds=%s",
            job.job_id,
            payload.delay_seconds,
        )
    except Exception as exc:  # noqa: BLE001
        job_service.mark_failed(db, job, f"Queue enqueue failed: {exc}")
        LogService.log_action(
            db,
            actor_employee_id=employee.employee_id,
            user_role="ENGINEER",
            action_type="ENQUEUE_REPORT_JOB_DELAYED",
            entity_type="background_jobs",
            entity_id=str(job.job_id),
            status=LogStatus.FAILED,
            details={"task_id": payload.task_id, "delay_seconds": payload.delay_seconds, "error": str(exc)},
        )
        db.commit()
        db.refresh(job)
        logger.exception("Delayed report job enqueue failed: job_id=%s", job.job_id)
    return BackgroundJobResponse.model_validate(job)
