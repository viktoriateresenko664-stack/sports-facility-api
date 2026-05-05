from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.schemas.bff import DesktopDashboardResponse, DesktopFacilityItem


class DesktopDashboardQueryService:
    @staticmethod
    def get_dashboard(db: Session) -> DesktopDashboardResponse:
        rows = db.execute(
            text(
                """
                SELECT
                    facility_id AS id,
                    name,
                    facility_type AS type,
                    address,
                    status::text AS status,
                    latitude,
                    longitude
                FROM sports_facilities
                ORDER BY facility_id
                """
            )
        ).mappings().all()
        facilities = [DesktopFacilityItem.model_validate(dict(row)) for row in rows]
        return DesktopDashboardResponse(facilities=facilities)
