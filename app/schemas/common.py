from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    service: str = "sports-facility-api"
