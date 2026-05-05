from __future__ import annotations

import json
import random
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import and_, func
from sqlalchemy.orm import Session, joinedload

from app.core.status_normalization import normalize_alert_status
from app.models.enums import SensorDataStatus
from app.models.equipment import Equipment
from app.models.sensor_data import SensorData
from app.models.sports_facility import SportsFacility
from app.services.sensor_degradation_service import sensor_degradation_service
from app.services.sensor_simulator_service import evaluate_sensor_value


def _format_value(sensor_type: str, value: float) -> str:
    kind = (sensor_type or "").strip().lower()
    if kind == "temperature":
        return f"{round(value, 1)}°C"
    if kind == "humidity":
        return f"{round(value, 1)}%"
    if kind == "voltage":
        return f"{round(value, 1)}V"
    if kind == "pressure":
        return f"{round(value, 2)}bar"
    return str(round(value, 2))


def _default_unit(sensor_type: str) -> str:
    kind = (sensor_type or "").strip().lower()
    if kind == "temperature":
        return "°C"
    if kind == "humidity":
        return "%"
    if kind == "voltage":
        return "V"
    if kind == "pressure":
        return "bar"
    return ""


def _generate_base_value(sensor_type: str, *, sensor_key: str | int | None = None) -> float:
    kind = (sensor_type or "").strip().lower()
    if kind == "temperature":
        return round(sensor_degradation_service.apply(sensor_type, random.uniform(-5, 35), sensor_key=sensor_key), 2)
    if kind == "humidity":
        return round(sensor_degradation_service.apply(sensor_type, random.uniform(20, 95), sensor_key=sensor_key), 2)
    if kind == "voltage":
        return round(sensor_degradation_service.apply(sensor_type, random.uniform(190, 240), sensor_key=sensor_key), 2)
    if kind == "pressure":
        return round(sensor_degradation_service.apply(sensor_type, random.uniform(1.0, 4.0), sensor_key=sensor_key), 2)
    return round(sensor_degradation_service.apply(sensor_type, random.uniform(0, 100), sensor_key=sensor_key), 2)


def _latest_sensor_data_map(db: Session) -> dict[int, SensorData]:
    latest_subquery = (
        db.query(
            SensorData.sensor_id.label("sensor_id"),
            func.max(SensorData.measured_at).label("latest_at"),
        )
        .group_by(SensorData.sensor_id)
        .subquery()
    )

    rows = (
        db.query(SensorData)
        .join(
            latest_subquery,
            and_(
                SensorData.sensor_id == latest_subquery.c.sensor_id,
                SensorData.measured_at == latest_subquery.c.latest_at,
            ),
        )
        .all()
    )
    return {row.sensor_id: row for row in rows}


def _map_status(status: SensorDataStatus) -> tuple[str, int]:
    if status == SensorDataStatus.CRITICAL:
        return "CRITICAL", 2
    if status == SensorDataStatus.ALERT:
        return "WARNING", 1
    return "NORMAL", 0


def build_fake_sensor_payload(
    db: Session,
    *,
    randomize: bool = False,
    write_to_db: bool = False,
) -> dict[str, Any]:
    facilities = (
        db.query(SportsFacility)
        .options(
            joinedload(SportsFacility.equipment_items).joinedload(Equipment.sensors),
        )
        .order_by(SportsFacility.facility_id.asc())
        .all()
    )

    latest_data_by_sensor = _latest_sensor_data_map(db)
    sensor_degradation_service.sync_sensor_catalog(
        [
            (int(sensor.sensor_id), int(facility.facility_id), str(sensor.sensor_type or ""))
            for facility in facilities
            for eq in facility.equipment_items
            for sensor in eq.sensors
        ]
    )

    response: dict[str, Any] = {"facilities": []}
    new_rows: list[SensorData] = []

    for facility in facilities:
        facility_equipment = []
        facility_sensors = []
        facility_alert_level = 0

        for eq in facility.equipment_items:
            eq_alert_level = 0

            for sensor in eq.sensors:
                latest = latest_data_by_sensor.get(sensor.sensor_id)

                if latest is not None:
                    raw_value = float(latest.value)
                    state, alert_level = _map_status(latest.status)
                else:
                    raw_value = _generate_base_value(sensor.sensor_type, sensor_key=sensor.sensor_id)
                    evaluation = evaluate_sensor_value(sensor.sensor_type, raw_value)
                    state = evaluation.status
                    alert_level = evaluation.alert_level

                if randomize:
                    jitter = 0.0
                    kind = (sensor.sensor_type or "").strip().lower()
                    if kind == "temperature":
                        jitter = random.uniform(-0.8, 0.8)
                    elif kind == "humidity":
                        jitter = random.uniform(-2.0, 2.0)
                    elif kind == "voltage":
                        jitter = random.uniform(-3.0, 3.0)
                    elif kind == "pressure":
                        jitter = random.uniform(-0.1, 0.1)
                    raw_value = sensor_degradation_service.apply(
                        sensor.sensor_type,
                        raw_value + jitter,
                        sensor_key=sensor.sensor_id,
                    )
                    evaluation = evaluate_sensor_value(sensor.sensor_type, raw_value)
                    state = evaluation.status
                    alert_level = evaluation.alert_level

                rounded_value = round(raw_value, 2)
                value_text = _format_value(sensor.sensor_type, rounded_value)
                unit = sensor.unit or _default_unit(sensor.sensor_type)
                state = normalize_alert_status(state) or "NORMAL"

                if write_to_db:
                    evaluation = evaluate_sensor_value(sensor.sensor_type, rounded_value)
                    new_rows.append(
                        SensorData(
                            sensor_id=sensor.sensor_id,
                            value=rounded_value,
                            status=evaluation.db_status,
                            measured_at=datetime.now(UTC),
                            meta=json.dumps(
                                {
                                    "status": evaluation.status,
                                    "alert_level": evaluation.alert_level,
                                    "source": "dev-fake-endpoint",
                                }
                            ),
                        )
                    )

                eq_alert_level = max(eq_alert_level, alert_level)
                facility_alert_level = max(facility_alert_level, alert_level)
                facility_sensors.append(
                    {
                        "sensor_id": sensor.sensor_id,
                        "name": sensor.sensor_code,
                        "type": sensor.sensor_type,
                        "value": value_text,
                        "raw_value": rounded_value,
                        "unit": unit,
                        "state": state,
                        "alert_level": alert_level,
                    }
                )

            eq_status = "NORMAL"
            if eq_alert_level == 2:
                eq_status = "CRITICAL"
            elif eq_alert_level == 1:
                eq_status = "WARNING"
            eq_status = normalize_alert_status(eq_status) or "NORMAL"

            facility_equipment.append(
                {
                    "equipment_id": eq.equipment_id,
                    "name": eq.name,
                    "type": eq.equipment_type,
                    "status": eq_status,
                }
            )

        facility_status = "NORMAL"
        if facility_alert_level == 2:
            facility_status = "CRITICAL"
        elif facility_alert_level == 1:
            facility_status = "WARNING"
        facility_status = normalize_alert_status(facility_status) or "NORMAL"

        response["facilities"].append(
            {
                "facility_id": facility.facility_id,
                "name": facility.name,
                "type": facility.facility_type,
                "address": facility.address,
                "latitude": facility.latitude,
                "longitude": facility.longitude,
                "description": facility.description,
                "status": facility_status,
                "equipment": facility_equipment,
                "sensors": facility_sensors,
            }
        )

    if write_to_db and new_rows:
        db.add_all(new_rows)
        db.commit()

    return response
