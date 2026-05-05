from datetime import datetime

from pydantic import BaseModel, ConfigDict


class SensorDataCreateRequest(BaseModel):
    sensor_id: int
    value: float
    model_config = ConfigDict(extra="forbid")


class SensorDataResponse(BaseModel):
    data_id: int
    sensor_id: int
    sensor_name: str
    sensor_type: str
    facility_id: int
    equipment_id: int
    value: float
    measurement_unit: str
    status: str
    alert_level: int
    measured_at: datetime


class SensorSimulatorStatusResponse(BaseModel):
    enabled: bool
    running: bool
    connected_ws_clients: int
    message: str
