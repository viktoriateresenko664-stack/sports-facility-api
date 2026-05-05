from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.db.session import get_db
from app.models.sports_facility import SportsFacility
from app.schemas.sports_facility import SportsFacilityResponse

router = APIRouter(prefix="/sports-facilities", tags=["sports-facilities"])
SPORTS_FACILITY_RESPONSES = {
    401: {"description": "Unauthorized"},
    403: {"description": "Forbidden"},
    404: {"description": "Not Found"},
}


@router.get(
    "",
    response_model=list[SportsFacilityResponse],
    responses=SPORTS_FACILITY_RESPONSES,
    summary="List Sports Facilities",
    description="Returns all sports facilities.",
)
def list_sports_facilities(
    db: Session = Depends(get_db),
    _=Depends(require_roles("USER", "ENGINEER", "OPERATOR", "CHIEF_ENGINEER")),
) -> list[SportsFacilityResponse]:
    rows = db.query(SportsFacility).order_by(SportsFacility.facility_id).all()
    return [SportsFacilityResponse.model_validate(row) for row in rows]


@router.get(
    "/{facility_id}",
    response_model=SportsFacilityResponse,
    responses=SPORTS_FACILITY_RESPONSES,
    summary="Get Sports Facility",
    description="Returns a sports facility by ID.",
)
def get_sports_facility(
    facility_id: int,
    db: Session = Depends(get_db),
    _=Depends(require_roles("USER", "ENGINEER", "OPERATOR", "CHIEF_ENGINEER")),
) -> SportsFacilityResponse:
    row = db.get(SportsFacility, facility_id)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sports facility not found")
    return SportsFacilityResponse.model_validate(row)
