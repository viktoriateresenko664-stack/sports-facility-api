from __future__ import annotations

import json
import random
import sys
from pathlib import Path
from datetime import UTC, datetime
from typing import Iterable

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.db.session import SessionLocal
from app.models.sensor import Sensor
from app.models.sensor_data import SensorData
from app.services.sensor_degradation_service import sensor_degradation_service
from app.services.sensor_simulator_service import evaluate_sensor_value
from sqlalchemy.orm import joinedload


def _generate_value(sensor_type: str, *, sensor_key: str | int | None = None) -> float:
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


def _create_rows(sensors: Iterable[Sensor]) -> list[SensorData]:
    rows: list[SensorData] = []
    for sensor in sensors:
        value = _generate_value(sensor.sensor_type, sensor_key=sensor.sensor_id)
        evaluation = evaluate_sensor_value(sensor.sensor_type, value)
        rows.append(
            SensorData(
                sensor_id=sensor.sensor_id,
                value=round(value, 2),
                status=evaluation.db_status,
                measured_at=datetime.now(UTC),
                meta=json.dumps(
                    {
                        "status": evaluation.status,
                        "alert_level": evaluation.alert_level,
                        "source": "script-generate-fake-sensor-data",
                    }
                ),
            )
        )
    return rows


def generate_fake_sensor_data_once() -> int:
    created = 0
    with SessionLocal() as db:
        sensors = (
            db.query(Sensor)
            .options(joinedload(Sensor.equipment))
            .order_by(Sensor.sensor_id.asc())
            .all()
        )
        sensor_degradation_service.sync_sensor_catalog(
            [
                (
                    int(sensor.sensor_id),
                    int(sensor.equipment.facility_id) if sensor.equipment is not None else None,
                    str(sensor.sensor_type or ""),
                )
                for sensor in sensors
            ]
        )
        rows = _create_rows(sensors)
        if rows:
            db.add_all(rows)
            db.commit()
            created = len(rows)
    return created


def main() -> None:
    created = generate_fake_sensor_data_once()
    print(f"Created {created} sensor_data rows")


if __name__ == "__main__":
    main()
