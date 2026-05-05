from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import AuthPrincipal, get_current_employee, require_roles
from app.core.pagination import resolve_pagination
from app.core.status_normalization import normalize_task_status
from app.db.session import get_db
from app.models.employee import Employee
from app.models.engineer_task import EngineerTask
from app.models.enums import TaskStatus
from app.schemas.engineer_task import (
    EngineerTaskCreate,
    EngineerTasksPageResponse,
    EngineerTaskRawResponse,
    EngineerTaskResponse,
    TaskStatusTransitionResponse,
)
from app.services.engineer_task_service import EngineerTaskService

router = APIRouter(prefix="/engineer-tasks", tags=["engineer-tasks"])
service = EngineerTaskService()
ENGINEER_TASK_RESPONSES = {
    400: {"description": "Bad Request"},
    401: {"description": "Unauthorized"},
    403: {"description": "Forbidden"},
    404: {"description": "Not Found"},
    409: {"description": "Conflict"},
}


@router.post(
    "",
    response_model=EngineerTaskResponse,
    responses=ENGINEER_TASK_RESPONSES,
    summary="Create Engineer Task",
    description="Creates a new engineer task and schedules a related background job.",
)
def create_engineer_task(
    payload: EngineerTaskCreate,
    db: Session = Depends(get_db),
    employee: Employee = Depends(get_current_employee),
    principal: AuthPrincipal = Depends(require_roles("ENGINEER", "OPERATOR", "CHIEF_ENGINEER", "ADMIN")),
) -> EngineerTaskResponse:
    is_privileged = bool({"OPERATOR", "CHIEF_ENGINEER", "ADMIN"}.intersection(set(principal.roles)))
    if not is_privileged and payload.assigned_engineer_id != employee.employee_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Engineer can create tasks only for self",
        )
    task, _job_id = service.create_task_with_background_job(db, payload, employee.employee_id)
    return EngineerTaskResponse.model_validate(task)


@router.get(
    "",
    response_model=list[EngineerTaskResponse] | EngineerTasksPageResponse,
    responses=ENGINEER_TASK_RESPONSES,
    summary="List Engineer Tasks",
    description="Returns all engineer tasks available to the current employee role.",
)
def list_engineer_tasks(
    status_filter: str | None = Query(default=None, alias="status"),
    facility_id: int | None = None,
    assigned_engineer: int | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    page: int | None = Query(default=None, ge=1),
    limit: int | None = Query(default=None, ge=1),
    db: Session = Depends(get_db),
    employee: Employee = Depends(get_current_employee),
    principal: AuthPrincipal = Depends(require_roles("ENGINEER", "OPERATOR", "CHIEF_ENGINEER", "ADMIN")),
) -> list[EngineerTaskResponse] | EngineerTasksPageResponse:
    if date_from and date_to and date_from > date_to:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="date_from must be before date_to")

    normalized_status = normalize_task_status(status_filter)
    if status_filter is not None and normalized_status is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported status filter")

    privileged = bool({"OPERATOR", "CHIEF_ENGINEER", "ADMIN"}.intersection(set(principal.roles)))
    target_engineer = assigned_engineer
    if not privileged:
        if assigned_engineer is not None and assigned_engineer != employee.employee_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Engineer can view only own tasks")
        target_engineer = employee.employee_id

    query = db.query(EngineerTask)
    if normalized_status is not None:
        query = query.filter(EngineerTask.status == TaskStatus(normalized_status))
    if facility_id is not None:
        query = query.filter(EngineerTask.facility_id == facility_id)
    if target_engineer is not None:
        query = query.filter(EngineerTask.assigned_engineer_id == target_engineer)
    if date_from is not None:
        query = query.filter(EngineerTask.created_at >= date_from)
    if date_to is not None:
        query = query.filter(EngineerTask.created_at <= date_to)

    query = query.order_by(EngineerTask.created_at.desc())
    pagination = resolve_pagination(page, limit)
    if pagination is None:
        rows = query.all()
        return [EngineerTaskResponse.model_validate(row) for row in rows]

    total = query.count()
    rows = query.offset(pagination.offset).limit(pagination.limit).all()
    return EngineerTasksPageResponse(
        items=[EngineerTaskResponse.model_validate(row) for row in rows],
        page=pagination.page,
        limit=pagination.limit,
        total=total,
    )


@router.get(
    "/raw",
    response_model=list[EngineerTaskRawResponse],
    responses=ENGINEER_TASK_RESPONSES,
    summary="List Engineer Tasks (Raw SQL)",
    description="Returns engineer tasks using a direct SQL read query without ORM.",
)
def list_engineer_tasks_raw(
    status_filter: TaskStatus | None = None,
    db: Session = Depends(get_db),
    employee: Employee = Depends(get_current_employee),
    principal: AuthPrincipal = Depends(require_roles("ENGINEER", "OPERATOR", "CHIEF_ENGINEER", "ADMIN")),
) -> list[EngineerTaskRawResponse]:
    query_sql = """
        SELECT
            task_id,
            facility_id,
            request_id,
            created_by_employee_id,
            assigned_engineer_id,
            description,
            operator_comment,
            status::text AS status,
            created_at,
            started_at,
            completed_at
        FROM engineer_tasks
        WHERE 1=1
    """
    params: dict[str, object] = {}
    if status_filter is not None:
        query_sql += " AND status::text = :status_filter"
        params["status_filter"] = status_filter.value
    if "ENGINEER" in principal.roles and not {"OPERATOR", "CHIEF_ENGINEER", "ADMIN"}.intersection(set(principal.roles)):
        query_sql += " AND assigned_engineer_id = :employee_id"
        params["employee_id"] = employee.employee_id
    query_sql += " ORDER BY created_at DESC"
    query = text(query_sql)
    rows = db.execute(query, params).mappings().all()
    return [EngineerTaskRawResponse.model_validate(dict(row)) for row in rows]


@router.get(
    "/{task_id}",
    response_model=EngineerTaskResponse,
    responses=ENGINEER_TASK_RESPONSES,
    summary="Get Engineer Task",
    description="Returns full details for a specific engineer task.",
)
def get_engineer_task(
    task_id: int,
    db: Session = Depends(get_db),
    employee: Employee = Depends(get_current_employee),
    principal: AuthPrincipal = Depends(require_roles("ENGINEER", "OPERATOR", "CHIEF_ENGINEER", "ADMIN")),
) -> EngineerTaskResponse:
    task = service.get_task(db, task_id)
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    if "ENGINEER" in principal.roles and not {"OPERATOR", "CHIEF_ENGINEER", "ADMIN"}.intersection(set(principal.roles)):
        if task.assigned_engineer_id != employee.employee_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return EngineerTaskResponse.model_validate(task)


@router.post(
    "/{task_id}/start",
    response_model=TaskStatusTransitionResponse,
    responses=ENGINEER_TASK_RESPONSES,
    summary="Start Engineer Task",
    description="Changes task status to IN_PROGRESS when transition rules allow it.",
)
def start_task(
    task_id: int,
    db: Session = Depends(get_db),
    employee: Employee = Depends(get_current_employee),
    principal: AuthPrincipal = Depends(require_roles("ENGINEER", "CHIEF_ENGINEER", "ADMIN")),
) -> TaskStatusTransitionResponse:
    task_before = service.get_task(db, task_id)
    if task_before and "ENGINEER" in principal.roles and not {"CHIEF_ENGINEER", "ADMIN"}.intersection(set(principal.roles)):
        if task_before.assigned_engineer_id != employee.employee_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    previous = task_before.status if task_before else None
    task = service.start_task(db, task_id)
    return TaskStatusTransitionResponse(
        task_id=task.task_id,
        previous_status=previous or task.status,
        current_status=task.status,
        changed_at=datetime.utcnow(),
    )


@router.post(
    "/{task_id}/finish",
    response_model=TaskStatusTransitionResponse,
    responses=ENGINEER_TASK_RESPONSES,
    summary="Finish Engineer Task",
    description="Changes task status to COMPLETED when transition rules allow it.",
)
def finish_task(
    task_id: int,
    db: Session = Depends(get_db),
    employee: Employee = Depends(get_current_employee),
    principal: AuthPrincipal = Depends(require_roles("ENGINEER", "CHIEF_ENGINEER", "ADMIN")),
) -> TaskStatusTransitionResponse:
    task_before = service.get_task(db, task_id)
    if task_before and "ENGINEER" in principal.roles and not {"CHIEF_ENGINEER", "ADMIN"}.intersection(set(principal.roles)):
        if task_before.assigned_engineer_id != employee.employee_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    previous = task_before.status if task_before else None
    task = service.finish_task(db, task_id)
    return TaskStatusTransitionResponse(
        task_id=task.task_id,
        previous_status=previous or task.status,
        current_status=task.status,
        changed_at=datetime.utcnow(),
    )


@router.post(
    "/{task_id}/cancel",
    response_model=TaskStatusTransitionResponse,
    responses=ENGINEER_TASK_RESPONSES,
    summary="Cancel Engineer Task",
    description="Changes task status to CANCELED when transition rules allow it.",
)
def cancel_task(
    task_id: int,
    db: Session = Depends(get_db),
    employee: Employee = Depends(get_current_employee),
    principal: AuthPrincipal = Depends(require_roles("ENGINEER", "OPERATOR", "CHIEF_ENGINEER", "ADMIN")),
) -> TaskStatusTransitionResponse:
    task_before = service.get_task(db, task_id)
    if task_before and "ENGINEER" in principal.roles and not {"OPERATOR", "CHIEF_ENGINEER", "ADMIN"}.intersection(set(principal.roles)):
        if task_before.assigned_engineer_id != employee.employee_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    previous = task_before.status if task_before else None
    task = service.cancel_task(db, task_id)
    return TaskStatusTransitionResponse(
        task_id=task.task_id,
        previous_status=previous or task.status,
        current_status=task.status,
        changed_at=datetime.utcnow(),
    )
