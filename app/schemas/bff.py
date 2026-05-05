from pydantic import BaseModel, ConfigDict, Field


class WebDashboardResponse(BaseModel):
    summary: str
    widgets: list[str]
    total_tasks: int
    active_tasks: int
    completed_tasks: int


class WebFacilityMapItem(BaseModel):
    facility_id: int
    name: str
    facility_type: str
    address: str
    status: str
    latitude: float | None = None
    longitude: float | None = None


class WebFacilitiesMapResponse(BaseModel):
    items: list[WebFacilityMapItem]


class WebUserRequestItem(BaseModel):
    request_id: int
    user_id: int
    facility_id: int
    title: str
    description: str
    status: str
    created_at: str


class MobileTaskSummary(BaseModel):
    total: int
    active: int
    completed: int
    created: int
    cancelled: int


class MobileTaskItem(BaseModel):
    task_id: int
    request_id: int | None
    title: str | None = None
    request_title: str | None = None
    facility_id: int
    facility_name: str
    facility_address: str
    description: str
    operator_comment: str | None
    status: str
    status_label: str
    created_at: str
    started_at: str | None
    completed_at: str | None


class MobileTasksResponse(BaseModel):
    # Backward-compatible legacy fields
    total: int
    active: int
    completed: int
    created: int
    cancelled: int
    # New shape
    summary: MobileTaskSummary
    tasks: list[MobileTaskItem]
    # Legacy extras retained
    quick_actions: list[str]


class DesktopMonitoringResponse(BaseModel):
    summary: str
    facilities_count: int
    tasks_count: int
    pending_jobs_count: int
    panels: list[str]


class DesktopFacilityItem(BaseModel):
    id: int
    name: str
    type: str
    address: str
    status: str
    latitude: float | None = None
    longitude: float | None = None


class DesktopDashboardResponse(BaseModel):
    facilities: list[DesktopFacilityItem]


class DesktopRequestItem(BaseModel):
    id: int
    title: str | None = None
    facility: str
    description: str
    date: str
    status: str
    engineer: str


class DesktopRequestsPageResponse(BaseModel):
    items: list[DesktopRequestItem]
    page: int
    limit: int
    total: int


class DesktopEmployeeItem(BaseModel):
    id: int
    name: str
    phone: str
    email: str
    position: str


class DesktopLogItem(BaseModel):
    id: int
    user: str
    role: str
    action: str
    object: str
    date: str
    status: str


class DesktopLogsPageResponse(BaseModel):
    items: list[DesktopLogItem]
    page: int
    limit: int
    total: int


class DesktopAssignEngineerRequest(BaseModel):
    assigned_engineer_id: int
    operator_comment: str | None = Field(default=None, max_length=4000)
    model_config = ConfigDict(extra="forbid")


class DesktopAssignEngineerResponse(BaseModel):
    request_id: int
    task_id: int
    assigned_engineer_id: int
    job_id: str
    status: str


class DesktopCreateSensorTaskRequest(BaseModel):
    facility_id: int
    assigned_engineer_id: int
    description: str = Field(min_length=3, max_length=4000)
    title: str | None = Field(default=None, max_length=255)
    equipment_id: int | None = None
    sensor_id: int | None = None
    operator_comment: str | None = Field(default=None, max_length=4000)
    model_config = ConfigDict(extra="forbid")


class DesktopCreateSensorTaskResponse(BaseModel):
    task_id: int
    facility_id: int
    assigned_engineer_id: int
    status: str
    job_id: str
    source: str


class DesktopReportItem(BaseModel):
    report_id: int
    task_id: int
    facility_id: int
    facility_name: str
    engineer_id: int
    engineer_name: str
    task_status: str
    source: str
    created_at: str
    original_filename: str | None = None
    content_type: str | None = None
    size_bytes: int | None = None
    download_url: str | None = None
    preview_url: str | None = None
    has_preview: bool = False


class DesktopReportsResponse(BaseModel):
    total: int
    page: int
    limit: int
    items: list[DesktopReportItem]


class DesktopReportDetailResponse(BaseModel):
    report_id: int
    task_id: int
    facility_id: int
    facility_name: str
    engineer_id: int
    engineer_name: str
    task_status: str
    source: str
    created_at: str
    report_text: str | None = None
    original_filename: str | None = None
    content_type: str | None = None
    size_bytes: int | None = None
    stored_relative_path: str | None = None
    download_url: str | None = None
    preview_url: str | None = None
    has_preview: bool = False
