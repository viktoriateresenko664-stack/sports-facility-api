from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class GenerateReportRequest(BaseModel):
    task_id: int
    report_type: str | None = Field(default="standard", min_length=1, max_length=120)
    notes: str | None = Field(default=None, max_length=4000)
    model_config = ConfigDict(extra="forbid")


class GenerateReportDelayedRequest(GenerateReportRequest):
    delay_seconds: int = Field(ge=1, le=86400)
    model_config = ConfigDict(extra="forbid")


class EngineerReportResponse(BaseModel):
    report_id: int
    task_id: int
    engineer_id: int
    report_text: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class EngineerReportFileResponse(BaseModel):
    report_id: int
    task_id: int
    engineer_id: int
    source: str
    created_at: datetime
    report_text: str | None = None
    original_filename: str | None = None
    content_type: str | None = None
    size_bytes: int | None = None
    download_url: str | None = None

    model_config = ConfigDict(extra="forbid")


class SeedReportsRequest(BaseModel):
    task_ids: list[int] = Field(default_factory=list, max_length=20)
    overwrite_existing: bool = False
    model_config = ConfigDict(extra="forbid")


class SeedReportsResponse(BaseModel):
    created_count: int
    updated_count: int
    skipped_count: int
    report_ids: list[int]
    model_config = ConfigDict(extra="forbid")


class EngineerReportsPageResponse(BaseModel):
    items: list[EngineerReportFileResponse]
    page: int
    limit: int
    total: int
    model_config = ConfigDict(extra="forbid")
