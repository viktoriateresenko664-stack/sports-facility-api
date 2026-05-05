from __future__ import annotations

import json
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.api.deps import require_roles
from app.core.config import settings
from app.core.status_normalization import normalize_alert_status
from app.db.session import get_db
from app.models.sensor import Sensor
from app.models.sensor_data import SensorData
from app.schemas.sensor import SensorDataCreateRequest, SensorDataResponse, SensorSimulatorStatusResponse
from app.services.sensor_simulator_service import (
    build_sensor_event,
    evaluate_sensor_value,
    sensor_simulator_service,
)
from app.services.sensor_stream_service import sensor_stream_service

router = APIRouter(prefix="/sensors", tags=["sensors"])
SENSORS_ROLES = ("ADMIN", "OPERATOR", "CHIEF_ENGINEER", "ENGINEER")


def _sim_status(message: str) -> SensorSimulatorStatusResponse:
    return SensorSimulatorStatusResponse(
        enabled=settings.sensor_simulator_enabled,
        running=sensor_simulator_service.is_running,
        connected_ws_clients=sensor_stream_service.connected_clients,
        message=message,
    )


@router.post(
    "/data",
    response_model=SensorDataResponse,
    summary="Create Sensor Data Point",
    description="Stores incoming sensor value, computes alert status and broadcasts websocket event.",
)
async def create_sensor_data(
    payload: SensorDataCreateRequest,
    db: Session = Depends(get_db),
    _=Depends(require_roles(*SENSORS_ROLES)),
) -> SensorDataResponse:
    if settings.sensor_source_mode == "fake_only":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Direct real sensor ingestion is disabled in fake_only mode",
        )

    sensor = (
        db.query(Sensor)
        .options(joinedload(Sensor.equipment))
        .filter(Sensor.sensor_id == payload.sensor_id)
        .first()
    )
    if not sensor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sensor not found")

    evaluation = evaluate_sensor_value(sensor.sensor_type, payload.value)
    measured_at = datetime.now(UTC)

    data_row = SensorData(
        sensor_id=sensor.sensor_id,
        value=payload.value,
        status=evaluation.db_status,
        measured_at=measured_at,
        meta=json.dumps(
            {
                "status": evaluation.status,
                "alert_level": evaluation.alert_level,
                "source": "api",
            }
        ),
    )
    db.add(data_row)
    db.commit()
    db.refresh(data_row)

    event = build_sensor_event(
        sensor=sensor,
        value=payload.value,
        evaluation=evaluation,
        measured_at=measured_at,
    )
    await sensor_stream_service.broadcast_json(event)

    return SensorDataResponse(
        data_id=data_row.data_id,
        sensor_id=sensor.sensor_id,
        sensor_name=sensor.sensor_code,
        sensor_type=sensor.sensor_type,
        facility_id=sensor.equipment.facility_id,
        equipment_id=sensor.equipment_id,
        value=payload.value,
        measurement_unit=sensor.unit or "",
        status=normalize_alert_status(evaluation.status) or "NORMAL",
        alert_level=evaluation.alert_level,
        measured_at=measured_at,
    )


@router.post(
    "/simulator/start",
    response_model=SensorSimulatorStatusResponse,
    summary="Start Sensor Simulator",
    description="Starts demo sensor stream simulator if enabled in config.",
)
async def start_sensor_simulator(_=Depends(require_roles(*SENSORS_ROLES))) -> SensorSimulatorStatusResponse:
    if not settings.sensor_simulator_enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Sensor simulator is disabled by config",
        )

    _started, message = await sensor_simulator_service.start()
    return _sim_status(message)


@router.post(
    "/simulator/stop",
    response_model=SensorSimulatorStatusResponse,
    summary="Stop Sensor Simulator",
    description="Stops running sensor simulator.",
)
async def stop_sensor_simulator(_=Depends(require_roles(*SENSORS_ROLES))) -> SensorSimulatorStatusResponse:
    _stopped, message = await sensor_simulator_service.stop()
    return _sim_status(message)


@router.get(
    "/simulator/status",
    response_model=SensorSimulatorStatusResponse,
    summary="Sensor Simulator Status",
    description="Returns current simulator and websocket clients status.",
)
async def sensor_simulator_status(_=Depends(require_roles(*SENSORS_ROLES))) -> SensorSimulatorStatusResponse:
    return _sim_status("ok")
