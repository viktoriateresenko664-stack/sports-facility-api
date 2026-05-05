from fastapi import APIRouter

from app.api.routes import (
    auth,
    bff_desktop,
    bff_mobile,
    bff_web,
    dev,
    facilities,
    engineer_tasks,
    jobs,
    reports,
    sensors,
    sports_facilities,
    user_requests,
    ws_sensors,
    ws_tasks,
)
from app.schemas.common import HealthResponse

router = APIRouter()


@router.get(
    "/health",
    tags=["health"],
    response_model=HealthResponse,
    summary="API Health Check",
    description="Returns health status for the API v1 namespace.",
)
def health_check() -> HealthResponse:
    return HealthResponse(status="ok")


router.include_router(auth.router)
router.include_router(user_requests.router)
router.include_router(engineer_tasks.router)
router.include_router(reports.router)
router.include_router(jobs.router)
router.include_router(bff_web.router)
router.include_router(bff_mobile.router)
router.include_router(bff_desktop.router)
router.include_router(sensors.router)
router.include_router(ws_sensors.router)
router.include_router(ws_tasks.router)
router.include_router(sports_facilities.router)
router.include_router(dev.router)
router.include_router(facilities.router)
