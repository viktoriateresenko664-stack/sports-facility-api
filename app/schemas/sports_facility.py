from datetime import date, datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import FacilityStatus


class SportsFacilityResponse(BaseModel):
    facility_id: int
    name: str
    facility_type: str
    address: str
    latitude: float | None = None
    longitude: float | None = None
    description: str | None
    opening_date: date | None
    status: FacilityStatus
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
