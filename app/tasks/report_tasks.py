from datetime import UTC, datetime
from uuid import UUID

from app.core.metrics import log_queue_metric
from app.db.session import SessionLocal
from app.domain.events import ReportGeneratedEvent
from app.models.engineer_report import EngineerReport
from app.models.engineer_task import EngineerTask
from app.models.enums import BackgroundJobStatus, LogStatus
from app.services.events import event_dispatcher
from app.tasks.celery_app import celery_app


@celery_app.task(name="generate_engineer_report_task")
def generate_engineer_report_task(
    job_id: str,
    task_id: int,
    engineer_id: int,
    notes: str | None = None,
    report_type: str | None = "standard",
) -> dict:
    db = SessionLocal()
    try:
        from app.models.background_job import BackgroundJob
        from app.models.system_action_log import SystemActionLog

        job = db.get(BackgroundJob, UUID(job_id))
        if not job:
            return {"error": "job not found"}

        job.status = BackgroundJobStatus.PROCESSING
        job.started_at = datetime.now(UTC)
        db.add(job)
        db.commit()
        log_queue_metric(queue_job_id=job_id, queue_status=job.status.value, error=None)

        report_text = f"Auto-generated report for task #{task_id}."
        if report_type:
            report_text += f" Report type: {report_type}."
        if notes:
            report_text += f" Notes: {notes}"

        task = db.get(EngineerTask, task_id)
        if not task:
            raise ValueError(f"Task not found: task_id={task_id}")
        if task.assigned_engineer_id != engineer_id:
            raise ValueError(
                f"Forbidden report generation: task_id={task_id} is not assigned to engineer_id={engineer_id}"
            )

        report = db.query(EngineerReport).filter(EngineerReport.task_id == task_id).first()
        if report is None:
            report = EngineerReport(task_id=task_id, engineer_id=engineer_id, report_text=report_text)
        else:
            report.engineer_id = engineer_id
            report.report_text = report_text
        db.add(report)

        job.status = BackgroundJobStatus.SUCCESS
        job.result = {"report_text": report_text, "task_id": task_id}
        job.finished_at = datetime.now(UTC)
        db.add(job)
        db.add(
            SystemActionLog(
                actor_employee_id=engineer_id,
                user_role="ENGINEER",
                action_type="COMPLETE_REPORT_JOB",
                entity_type="background_jobs",
                entity_id=job_id,
                status=LogStatus.SUCCESS,
                details={"task_id": task_id},
            )
        )
        db.commit()

        event_dispatcher.dispatch(
            db,
            ReportGeneratedEvent(
                aggregate_id=str(report.report_id),
                user_id=engineer_id,
                data={
                    "task_id": task_id,
                    "job_id": job_id,
                },
            ),
        )
        log_queue_metric(queue_job_id=job_id, queue_status=job.status.value, error=None)

        return {"job_id": job_id, "status": "SUCCESS", "report_id": report.report_id}
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        from app.models.background_job import BackgroundJob
        from app.models.system_action_log import SystemActionLog

        job = db.get(BackgroundJob, UUID(job_id))
        if job:
            job.status = BackgroundJobStatus.FAILED
            job.error = str(exc)
            job.finished_at = datetime.now(UTC)
            db.add(job)
            db.add(
                SystemActionLog(
                    actor_employee_id=engineer_id,
                    user_role="ENGINEER",
                    action_type="COMPLETE_REPORT_JOB",
                    entity_type="background_jobs",
                    entity_id=job_id,
                    status=LogStatus.FAILED,
                    details={"task_id": task_id, "error": str(exc)},
                )
            )
            db.commit()
            log_queue_metric(queue_job_id=job_id, queue_status=job.status.value, error=str(exc))
        raise
    finally:
        db.close()
