from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.employee import Employee
from app.models.enums import AccountType, RequestStatus
from app.models.user_request import UserRequest
from app.schemas.bff import DesktopAssignEngineerRequest, DesktopAssignEngineerResponse
from app.schemas.engineer_task import EngineerTaskCreate
from app.services.engineer_task_service import EngineerTaskService


class DesktopRequestCommandService:
    @staticmethod
    def assign_request(
        db: Session,
        *,
        principal_account_type: AccountType,
        principal_subject_id: int,
        request_id: int,
        payload: DesktopAssignEngineerRequest,
        task_service: EngineerTaskService,
    ) -> DesktopAssignEngineerResponse:
        if principal_account_type != AccountType.EMPLOYEE:
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
        task, job_id = task_service.create_task_with_background_job(db, task_payload, principal_subject_id)

        if request_obj.status == RequestStatus.CREATED:
            request_obj.status = RequestStatus.ASSIGNED
            db.add(request_obj)
            db.commit()

        return DesktopAssignEngineerResponse(
            request_id=request_id,
            task_id=task.task_id,
            assigned_engineer_id=task.assigned_engineer_id,
            job_id=job_id,
            status=task.status.value if hasattr(task.status, "value") else str(task.status),
        )
