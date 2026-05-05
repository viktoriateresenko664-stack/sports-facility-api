from app.services.queries.desktop_dashboard_queries import DesktopDashboardQueryService
from app.services.queries.desktop_reports_queries import DesktopReportsQueryService
from app.services.queries.desktop_requests_queries import DesktopRequestsQueryService
from app.services.queries.mobile_tasks_queries import MobileTasksQueryService
from app.services.queries.report_job_queries import ReportJobQueryService
from app.services.queries.web_dashboard_queries import WebDashboardQueryService

__all__ = [
    "DesktopDashboardQueryService",
    "DesktopReportsQueryService",
    "DesktopRequestsQueryService",
    "MobileTasksQueryService",
    "ReportJobQueryService",
    "WebDashboardQueryService",
]
