from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import RequestStatus


class UserRequestCreate(BaseModel):
    facility_id: int
    title: str = Field(min_length=3, max_length=255)
    description: str = Field(min_length=3, max_length=4000)
    model_config = ConfigDict(extra="forbid")


class UserRequestResponse(BaseModel):
    request_id: int
    user_id: int
    facility_id: int
    title: str
    description: str
    status: RequestStatus
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
