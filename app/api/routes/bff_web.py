from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.core.config import settings
from app.db.session import get_db
from app.core.cache import build_cache_key, cache
from app.models.user import User
from app.schemas.bff import WebDashboardResponse, WebFacilitiesMapResponse, WebFacilityMapItem, WebUserRequestItem

router = APIRouter(prefix="/bff/web", tags=["bff-web"])


@router.get(
    "/dashboard",
    response_model=WebDashboardResponse,
    summary="Get Web Dashboard Data",
    description="Returns widgets and summary information for the web dashboard.",
)
def web_dashboard(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    _=Depends(require_roles("USER")),
) -> WebDashboardResponse:
    key = build_cache_key(path="/bff/web/dashboard", user_id=user.user_id, role="USER", account_type="USER")
    if settings.enable_bff_cache:
        cached = cache.get(key)
        if cached:
            return WebDashboardResponse.model_validate(cached)
    counts = db.execute(
        text(
            """
            SELECT
                COUNT(*) AS total_tasks,
                SUM(CASE WHEN status::text = 'ACTIVE' THEN 1 ELSE 0 END) AS active_tasks,
                SUM(CASE WHEN status::text = 'COMPLETED' THEN 1 ELSE 0 END) AS completed_tasks
            FROM engineer_tasks
            """
        )
    ).mappings().one()
    response = WebDashboardResponse(
        summary="web dashboard",
        widgets=["facilities", "active_tasks", "alerts"],
        total_tasks=int(counts["total_tasks"] or 0),
        active_tasks=int(counts["active_tasks"] or 0),
        completed_tasks=int(counts["completed_tasks"] or 0),
    )
    if settings.enable_bff_cache:
        cache.set(key, response.model_dump(), ttl_seconds=30)
    return response


def _iso(dt: datetime | None) -> str:
    if not dt:
        return ""
    return dt.isoformat().replace("+00:00", "Z")


@router.get(
    "/user-requests/my",
    response_model=list[WebUserRequestItem],
    summary="Get My Requests (Web BFF)",
    description="Returns user requests with effective status derived from engineer task status when available.",
)
def web_my_requests(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    _=Depends(require_roles("USER")),
) -> list[WebUserRequestItem]:
    rows = db.execute(
        text(
            """
            SELECT
                ur.request_id,
                ur.user_id,
                ur.facility_id,
                ur.title,
                ur.description,
                ur.status::text AS status,
                ur.created_at
            FROM user_requests ur
            WHERE ur.user_id = :user_id
            ORDER BY ur.created_at DESC
            """
        ),
        {"user_id": user.user_id},
    ).mappings().all()
    return [
        WebUserRequestItem(
            request_id=int(row["request_id"]),
            user_id=int(row["user_id"]),
            facility_id=int(row["facility_id"]),
            title=str(row["title"] or ""),
            description=str(row["description"] or ""),
            status=str(row["status"] or "CREATED"),
            created_at=_iso(row.get("created_at")),
        )
        for row in rows
    ]


@router.get(
    "/facilities-map",
    response_model=WebFacilitiesMapResponse,
    summary="Get Facilities For Map",
    description="Returns sports facilities with coordinates for map rendering on web clients.",
)
def web_facilities_map(
    only_with_coordinates: bool = True,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    _=Depends(require_roles("USER")),
) -> WebFacilitiesMapResponse:
    _ = user
    query_sql = """
        SELECT
            facility_id,
            name,
            facility_type,
            address,
            status::text AS status,
            latitude,
            longitude
        FROM sports_facilities
    """
    params: dict[str, object] = {}
    if only_with_coordinates:
        query_sql += " WHERE latitude IS NOT NULL AND longitude IS NOT NULL"
    query_sql += " ORDER BY facility_id"
    rows = db.execute(text(query_sql), params).mappings().all()
    return WebFacilitiesMapResponse(
        items=[
            WebFacilityMapItem(
                facility_id=int(row["facility_id"]),
                name=str(row["name"] or ""),
                facility_type=str(row["facility_type"] or ""),
                address=str(row["address"] or ""),
                status=str(row["status"] or ""),
                latitude=float(row["latitude"]) if row["latitude"] is not None else None,
                longitude=float(row["longitude"]) if row["longitude"] is not None else None,
            )
            for row in rows
        ]
    )
