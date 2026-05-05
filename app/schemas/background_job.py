from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.enums import AccountType, BackgroundJobStatus


class BackgroundJobPayload(BaseModel):
    task_id: int | None = None
    notes: str | None = None
    delay_seconds: int | None = None


class BackgroundJobResult(BaseModel):
    task_id: int | None = None
    report_text: str | None = None
    message: str | None = None
    job_id: UUID | None = None
    status: str | None = None
    report_id: int | None = None


class BackgroundJobResponse(BaseModel):
    job_id: UUID
    owner_id: int
    owner_type: AccountType
    task_id: int | None
    task_name: str
    status: BackgroundJobStatus
    payload: BackgroundJobPayload | None
    result: BackgroundJobResult | None
    error: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ReportJobStatusResponse(BaseModel):
    job_id: str
    status: str
    report_id: int | None = None
    error: str | None = None
    model_config = ConfigDict(extra="forbid")
