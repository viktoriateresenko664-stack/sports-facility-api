from __future__ import annotations

import logging
from typing import Callable

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import AuthPrincipal
from app.core.sanitizer import sanitize_text
from app.domain.events import ReportGenerationStartedEvent, ReportUploadedEvent
from app.models.employee import Employee
from app.models.engineer_report import EngineerReport
from app.models.engineer_task import EngineerTask
from app.models.enums import AccountType, LogStatus
from app.schemas.background_job import BackgroundJobResponse
from app.schemas.engineer_report import (
    EngineerReportFileResponse,
    GenerateReportDelayedRequest,
    GenerateReportRequest,
)
from app.services.background_job_service import BackgroundJobService
from app.services.domain_event_service import DomainEventService
from app.services.events import event_dispatcher
from app.services.incident_recovery_service import incident_recovery_service
from app.services.log_service import LogService
from app.services.report_service import ReportService
from app.services.task_stream_service import task_stream_service


class ReportCommandService:
    @staticmethod
    def upload_report_file(
        db: Session,
        *,
        task_id: int,
        notes: str | None,
        report_file: UploadFile,
        idempotency_key: str | None,
        employee: Employee,
        principal: AuthPrincipal,
        get_accessible_task_or_404: Callable[[Session, int, Employee, AuthPrincipal, bool], EngineerTask],
        to_report_file_response: Callable[[EngineerReport], EngineerReportFileResponse],
        report_service=ReportService,
        log_service=LogService,
        recovery_service=incident_recovery_service,
        cache_backend=None,
        task_stream=None,
        logger: logging.Logger | None = None,
    ) -> EngineerReportFileResponse:
        if cache_backend is None:
            from app.core.cache import cache as cache_backend  # local import to keep service decoupled
        if task_stream is None:
            task_stream = task_stream_service
        if logger is None:
            logger = logging.getLogger(__name__)

        normalized_key = (idempotency_key or "").strip() or None
        if normalized_key and len(normalized_key) > 128:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Idempotency-Key is too long (max 128)")

        task = get_accessible_task_or_404(db, task_id, employee, principal, True)
        existing_report = (
            db.query(EngineerReport)
            .filter(EngineerReport.task_id == task.task_id)
            .with_for_update()
            .first()
        )
        existing_metadata = (
            report_service.parse_uploaded_file_metadata(existing_report.report_text)
            if existing_report is not None
            else None
        )
        existing_key = (
            str(existing_metadata.get("idempotency_key")).strip()
            if existing_metadata and existing_metadata.get("idempotency_key")
            else None
        )

        if normalized_key and existing_report is not None and existing_key == normalized_key:
            log_service.log_action(
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
            return to_report_file_response(existing_report)

        metadata = report_service.save_uploaded_file(task.task_id, report_file)
        if existing_metadata and report_service.metadata_represents_same_file(existing_metadata, metadata):
            report_service.delete_stored_file_by_metadata(metadata)
            if existing_report is not None:
                log_service.log_action(
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
                return to_report_file_response(existing_report)

        report_text = report_service.metadata_to_text(
            metadata=metadata,
            uploaded_by_engineer_id=employee.employee_id,
            notes=notes,
            idempotency_key=normalized_key,
        )
        previous_metadata = existing_metadata
        recovery_stats: dict[str, int] | None = None
        try:
            report = report_service.upsert_report_text(
                db,
                task_id=task.task_id,
                engineer_id=task.assigned_engineer_id,
                report_text=report_text,
                commit=False,
            )
            recovery_stats = recovery_service.normalize_facility_sensors(
                db,
                facility_id=task.facility_id,
                source="report_uploaded",
                task_id=task.task_id,
            )
            log_service.log_action(
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
            report_service.delete_stored_file_by_metadata(metadata)
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Report already exists for this task") from exc
        except Exception:
            db.rollback()
            report_service.delete_stored_file_by_metadata(metadata)
            raise

        if previous_metadata and not report_service.metadata_represents_same_file(previous_metadata, metadata):
            report_service.delete_stored_file_by_metadata(previous_metadata)

        cache_backend.invalidate(prefix="/bff/")
        task_stream.publish_event(
            "REPORT_READY",
            {
                "report_id": report.report_id,
                "task_id": report.task_id,
                "engineer_id": report.engineer_id,
                "source": "uploaded_file",
            },
        )
        event_dispatcher.dispatch(
            db,
            ReportUploadedEvent(
                aggregate_id=str(report.report_id),
                user_id=employee.employee_id,
                data={"task_id": report.task_id},
            ),
        )
        logger.info("Report file uploaded: task_id=%s report_id=%s", task.task_id, report.report_id)
        return to_report_file_response(report)

    @staticmethod
    def generate_report(
        db: Session,
        *,
        payload: GenerateReportRequest,
        employee: Employee,
        principal: AuthPrincipal,
        get_accessible_task_or_404: Callable[[Session, int, Employee, AuthPrincipal, bool], EngineerTask],
        job_service: BackgroundJobService,
        domain_event_service=DomainEventService,
        log_service=LogService,
        cache_backend=None,
        queue_task=None,
        logger: logging.Logger | None = None,
    ) -> BackgroundJobResponse:
        if cache_backend is None:
            from app.core.cache import cache as cache_backend
        if logger is None:
            logger = logging.getLogger(__name__)

        get_accessible_task_or_404(db, payload.task_id, employee, principal, False)
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
        log_service.log_action(
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
        event = domain_event_service.publish(
            db,
            event_type="REPORT_GENERATION_REQUESTED",
            aggregate_type="background_jobs",
            aggregate_id=str(job.job_id),
            payload={"task_id": payload.task_id},
        )
        db.commit()
        domain_event_service.enqueue(str(event.event_id))
        cache_backend.invalidate(prefix="/bff/")

        if queue_task is None:
            from app.tasks.report_tasks import generate_engineer_report_task as queue_task

        try:
            queue_task.apply_async(
                args=[
                    str(job.job_id),
                    payload.task_id,
                    employee.employee_id,
                    sanitize_text(payload.notes),
                    sanitize_text(payload.report_type),
                ],
                ignore_result=True,
            )
            event_dispatcher.dispatch(
                db,
                ReportGenerationStartedEvent(
                    aggregate_id=str(job.job_id),
                    user_id=employee.employee_id,
                    data={"task_id": payload.task_id, "delay_seconds": None},
                ),
            )
            logger.info("Report job enqueued: job_id=%s", job.job_id)
        except Exception as exc:  # noqa: BLE001
            job_service.mark_failed(db, job, f"Queue enqueue failed: {exc}")
            log_service.log_action(
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

    @staticmethod
    def generate_report_delayed(
        db: Session,
        *,
        payload: GenerateReportDelayedRequest,
        employee: Employee,
        principal: AuthPrincipal,
        get_accessible_task_or_404: Callable[[Session, int, Employee, AuthPrincipal, bool], EngineerTask],
        job_service: BackgroundJobService,
        domain_event_service=DomainEventService,
        log_service=LogService,
        cache_backend=None,
        queue_task=None,
        logger: logging.Logger | None = None,
    ) -> BackgroundJobResponse:
        if cache_backend is None:
            from app.core.cache import cache as cache_backend
        if logger is None:
            logger = logging.getLogger(__name__)

        get_accessible_task_or_404(db, payload.task_id, employee, principal, False)
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
        log_service.log_action(
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
        event = domain_event_service.publish(
            db,
            event_type="REPORT_GENERATION_DELAYED_REQUESTED",
            aggregate_type="background_jobs",
            aggregate_id=str(job.job_id),
            payload={"task_id": payload.task_id, "delay_seconds": payload.delay_seconds},
        )
        db.commit()
        domain_event_service.enqueue(str(event.event_id))
        cache_backend.invalidate(prefix="/bff/")

        if queue_task is None:
            from app.tasks.report_tasks import generate_engineer_report_task as queue_task

        try:
            queue_task.apply_async(
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
            event_dispatcher.dispatch(
                db,
                ReportGenerationStartedEvent(
                    aggregate_id=str(job.job_id),
                    user_id=employee.employee_id,
                    data={
                        "task_id": payload.task_id,
                        "delay_seconds": payload.delay_seconds,
                    },
                ),
            )
            logger.info(
                "Delayed report job enqueued: job_id=%s delay_seconds=%s",
                job.job_id,
                payload.delay_seconds,
            )
        except Exception as exc:  # noqa: BLE001
            job_service.mark_failed(db, job, f"Queue enqueue failed: {exc}")
            log_service.log_action(
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
