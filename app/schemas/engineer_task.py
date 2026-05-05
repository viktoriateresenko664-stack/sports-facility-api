from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import TaskStatus


class EngineerTaskCreate(BaseModel):
    facility_id: int
    request_id: int | None = None
    assigned_engineer_id: int
    description: str = Field(min_length=3, max_length=4000)
    operator_comment: str | None = Field(default=None, min_length=0, max_length=4000)
    model_config = ConfigDict(extra="forbid")

    @field_validator("request_id", mode="before")
    @classmethod
    def normalize_request_id(cls, v: int | None) -> int | None:
        if v is None:
            return None
        try:
            iv = int(v)
        except (TypeError, ValueError):
            return None
        return None if iv <= 0 else iv


class EngineerTaskResponse(BaseModel):
    task_id: int
    facility_id: int
    request_id: int | None
    created_by_employee_id: int
    assigned_engineer_id: int
    description: str
    operator_comment: str | None
    status: TaskStatus
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class TaskStatusTransitionResponse(BaseModel):
    task_id: int
    previous_status: TaskStatus
    current_status: TaskStatus
    changed_at: datetime


class EngineerTaskRawResponse(BaseModel):
    task_id: int
    facility_id: int
    request_id: int | None
    created_by_employee_id: int
    assigned_engineer_id: int
    description: str
    operator_comment: str | None
    status: TaskStatus
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    model_config = ConfigDict(extra="forbid")


class EngineerTasksPageResponse(BaseModel):
    items: list[EngineerTaskResponse]
    page: int
    limit: int
    total: int
    model_config = ConfigDict(extra="forbid")
