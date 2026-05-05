import logging
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.engineer_task import EngineerTask
from app.models.enums import AccountType, LogStatus, RequestStatus, TaskStatus
from app.models.user_request import UserRequest
from app.repositories.engineer_task_repository import EngineerTaskRepository
from app.schemas.engineer_task import EngineerTaskCreate
from app.services.domain_event_service import DomainEventService
from app.services.background_job_service import BackgroundJobService
from app.services.incident_recovery_service import incident_recovery_service
from app.services.log_service import LogService
from app.services.task_stream_service import task_stream_service
from app.core.cache import cache
from app.core.sanitizer import sanitize_text

logger = logging.getLogger(__name__)


class InvalidTaskTransitionError(Exception):
    pass


ALLOWED_TRANSITIONS: dict[TaskStatus, set[TaskStatus]] = {
    TaskStatus.CREATED: {TaskStatus.ACTIVE},
    TaskStatus.ACTIVE: {TaskStatus.COMPLETED, TaskStatus.CANCELLED},
    TaskStatus.COMPLETED: set(),
    TaskStatus.CANCELLED: set(),
}


class EngineerTaskService:
    def __init__(self) -> None:
        self.repo = EngineerTaskRepository()
        self.job_service = BackgroundJobService()

    def can_transition(self, current_status: TaskStatus, target_status: TaskStatus) -> bool:
        return target_status in ALLOWED_TRANSITIONS.get(current_status, set())

    @staticmethod
    def _request_status_for_task(target_status: TaskStatus) -> RequestStatus:
        if target_status == TaskStatus.CREATED:
            return RequestStatus.ASSIGNED
        if target_status == TaskStatus.ACTIVE:
            return RequestStatus.IN_WORK
        if target_status == TaskStatus.COMPLETED:
            return RequestStatus.COMPLETED
        if target_status == TaskStatus.CANCELLED:
            return RequestStatus.CANCELLED
        return RequestStatus.ACTIVE

    def _change_status(self, db: Session, task_id: int, target_status: TaskStatus) -> EngineerTask:
        task = self.repo.get_by_id(db, task_id)
        if not task:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

        current_status = task.status
        if not self.can_transition(current_status, target_status):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Invalid transition: {current_status.value} -> {target_status.value}",
            )

        now = datetime.now(UTC)
        task.status = target_status
        if target_status == TaskStatus.ACTIVE:
            task.started_at = now
        if target_status in {TaskStatus.COMPLETED, TaskStatus.CANCELLED}:
            task.completed_at = now

        if task.request_id is not None:
            request_obj = db.get(UserRequest, task.request_id)
            if request_obj:
                request_obj.status = self._request_status_for_task(target_status)
                db.add(request_obj)

        recovery_stats: dict[str, int] | None = None
        if target_status == TaskStatus.COMPLETED:
            recovery_stats = incident_recovery_service.normalize_facility_sensors(
                db,
                facility_id=task.facility_id,
                source="task_completed",
                task_id=task.task_id,
            )

        db.add(task)
        LogService.log_action(
            db,
            actor_employee_id=task.assigned_engineer_id,
            user_role="ENGINEER",
            action_type="TASK_STATUS_CHANGE",
            entity_type="engineer_tasks",
            entity_id=str(task.task_id),
            status=LogStatus.SUCCESS,
            details={
                "from": current_status.value,
                "to": target_status.value,
                "sensor_recovery": recovery_stats,
            },
        )
        event = DomainEventService.publish(
            db,
            event_type="ENGINEER_TASK_STATUS_CHANGED",
            aggregate_type="engineer_tasks",
            aggregate_id=str(task.task_id),
            payload={"from": current_status.value, "to": target_status.value},
        )
        db.commit()
        db.refresh(task)
        if target_status == TaskStatus.ACTIVE:
            task_stream_service.publish_event(
                "TASK_STARTED",
                {
                    "task_id": task.task_id,
                    "request_id": task.request_id,
                    "facility_id": task.facility_id,
                    "assigned_engineer_id": task.assigned_engineer_id,
                    "status": task.status.value,
                },
            )
            task_stream_service.publish_event(
                "TASK_UPDATED",
                {
                    "task_id": task.task_id,
                    "request_id": task.request_id,
                    "facility_id": task.facility_id,
                    "assigned_engineer_id": task.assigned_engineer_id,
                    "status": task.status.value,
                    "previous_status": current_status.value,
                },
            )
        elif target_status == TaskStatus.COMPLETED:
            task_stream_service.publish_event(
                "TASK_COMPLETED",
                {
                    "task_id": task.task_id,
                    "request_id": task.request_id,
                    "facility_id": task.facility_id,
                    "assigned_engineer_id": task.assigned_engineer_id,
                    "status": task.status.value,
                },
            )
            task_stream_service.publish_event(
                "TASK_UPDATED",
                {
                    "task_id": task.task_id,
                    "request_id": task.request_id,
                    "facility_id": task.facility_id,
                    "assigned_engineer_id": task.assigned_engineer_id,
                    "status": task.status.value,
                    "previous_status": current_status.value,
                },
            )
        elif target_status == TaskStatus.CANCELLED:
            task_stream_service.publish_event(
                "TASK_CANCELLED",
                {
                    "task_id": task.task_id,
                    "request_id": task.request_id,
                    "facility_id": task.facility_id,
                    "assigned_engineer_id": task.assigned_engineer_id,
                    "status": task.status.value,
                },
            )
            task_stream_service.publish_event(
                "TASK_UPDATED",
                {
                    "task_id": task.task_id,
                    "request_id": task.request_id,
                    "facility_id": task.facility_id,
                    "assigned_engineer_id": task.assigned_engineer_id,
                    "status": task.status.value,
                    "previous_status": current_status.value,
                },
            )
        DomainEventService.enqueue(str(event.event_id))
        cache.invalidate(prefix="/bff/")
        logger.info("Task status changed: task_id=%s %s->%s", task.task_id, current_status, target_status)
        return task

    def start_task(self, db: Session, task_id: int) -> EngineerTask:
        return self._change_status(db, task_id, TaskStatus.ACTIVE)

    def finish_task(self, db: Session, task_id: int) -> EngineerTask:
        return self._change_status(db, task_id, TaskStatus.COMPLETED)

    def cancel_task(self, db: Session, task_id: int) -> EngineerTask:
        return self._change_status(db, task_id, TaskStatus.CANCELLED)

    def get_task(self, db: Session, task_id: int) -> EngineerTask | None:
        return self.repo.get_by_id(db, task_id)

    def list_tasks(self, db: Session) -> list[EngineerTask]:
        return self.repo.list_all(db)

    def create_task_with_background_job(
        self,
        db: Session,
        payload: EngineerTaskCreate,
        created_by_employee_id: int,
    ) -> tuple[EngineerTask, str]:
        try:
            if payload.request_id is not None:
                request_obj = db.get(UserRequest, payload.request_id)
                if not request_obj:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"User request with id={payload.request_id} not found",
                    )

            task = EngineerTask(
                facility_id=payload.facility_id,
                request_id=payload.request_id,
                created_by_employee_id=created_by_employee_id,
                assigned_engineer_id=payload.assigned_engineer_id,
                description=sanitize_text(payload.description) or "",
                operator_comment=sanitize_text(payload.operator_comment),
                status=TaskStatus.CREATED,
            )
            self.repo.create(db, task)
            if payload.operator_comment == "__FAIL_JOB__":
                raise RuntimeError("Forced job creation failure for transaction test")
            if task.request_id is not None:
                request_obj.status = RequestStatus.ASSIGNED
                db.add(request_obj)
            job = self.job_service.create_job(
                db,
                owner_id=created_by_employee_id,
                owner_type=AccountType.EMPLOYEE,
                task_id=task.task_id,
                task_name="engineer_task_post_create",
                payload={"task_id": task.task_id},
            )
            LogService.log_action(
                db,
                actor_employee_id=created_by_employee_id,
                user_role="OPERATOR",
                action_type="CREATE_ENGINEER_TASK",
                entity_type="engineer_tasks",
                entity_id=str(task.task_id),
                status=LogStatus.SUCCESS,
                details={"job_id": str(job.job_id)},
            )
            event = DomainEventService.publish(
                db,
                event_type="ENGINEER_TASK_CREATED",
                aggregate_type="engineer_tasks",
                aggregate_id=str(task.task_id),
                payload={"task_id": task.task_id, "job_id": str(job.job_id)},
            )
            db.commit()
            db.refresh(task)
            db.refresh(job)
            task_stream_service.publish_event(
                "TASK_CREATED",
                {
                    "task_id": task.task_id,
                    "request_id": task.request_id,
                    "facility_id": task.facility_id,
                    "assigned_engineer_id": task.assigned_engineer_id,
                    "status": task.status.value,
                },
            )
            task_stream_service.publish_event(
                "TASK_ASSIGNED",
                {
                    "task_id": task.task_id,
                    "request_id": task.request_id,
                    "facility_id": task.facility_id,
                    "assigned_engineer_id": task.assigned_engineer_id,
                    "status": task.status.value,
                },
            )
            task_stream_service.publish_event(
                "TASK_UPDATED",
                {
                    "task_id": task.task_id,
                    "request_id": task.request_id,
                    "facility_id": task.facility_id,
                    "assigned_engineer_id": task.assigned_engineer_id,
                    "status": task.status.value,
                    "previous_status": None,
                },
            )
            DomainEventService.enqueue(str(event.event_id))
            cache.invalidate(prefix="/bff/")
            logger.info("Engineer task created: task_id=%s job_id=%s", task.task_id, job.job_id)
            return task, str(job.job_id)
        except Exception:  # noqa: BLE001
            db.rollback()
            LogService.log_action(
                db,
                actor_employee_id=created_by_employee_id,
                user_role="OPERATOR",
                action_type="CREATE_ENGINEER_TASK",
                entity_type="engineer_tasks",
                entity_id=str(payload.request_id or payload.facility_id),
                status=LogStatus.FAILED,
                message="Transaction failed",
            )
            db.commit()
            logger.exception("Create engineer task transaction failed")
            raise
