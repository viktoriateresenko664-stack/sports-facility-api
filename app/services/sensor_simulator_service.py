from __future__ import annotations

import asyncio
import json
import random
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.orm import joinedload

from app.db.session import SessionLocal
from app.core.status_normalization import normalize_alert_status
from app.models.sensor import Sensor
from app.models.sensor_data import SensorData
from app.models.enums import SensorDataStatus
from app.services.sensor_degradation_service import sensor_degradation_service
from app.services.sensor_stream_service import sensor_stream_service


@dataclass
class SensorEvaluation:
    status: str
    alert_level: int
    db_status: SensorDataStatus


def evaluate_sensor_value(sensor_type: str, value: float) -> SensorEvaluation:
    sensor_kind = sensor_type.strip().lower()
    status = "NORMAL"
    alert_level = 0

    if sensor_kind == "temperature":
        if value > 35:
            status, alert_level = "CRITICAL", 2
        elif value >= 26:
            status, alert_level = "WARNING", 1
    elif sensor_kind == "humidity":
        if value > 75:
            status, alert_level = "CRITICAL", 2
        elif value >= 61:
            status, alert_level = "WARNING", 1
    elif sensor_kind == "voltage":
        if value < 190 or value > 245:
            status, alert_level = "CRITICAL", 2
        elif 190 <= value <= 209 or 231 <= value <= 245:
            status, alert_level = "WARNING", 1
    elif sensor_kind == "pressure":
        if value > 3.0:
            status, alert_level = "CRITICAL", 2
        elif value >= 2.6:
            status, alert_level = "WARNING", 1

    db_status = SensorDataStatus.NORMAL
    if status == "WARNING":
        db_status = SensorDataStatus.ALERT
    elif status == "CRITICAL":
        db_status = SensorDataStatus.CRITICAL

    return SensorEvaluation(status=status, alert_level=alert_level, db_status=db_status)


def build_sensor_event(sensor: Sensor, value: float, evaluation: SensorEvaluation, measured_at: datetime) -> dict:
    normalized_status = normalize_alert_status(evaluation.status) or "NORMAL"
    return {
        "type": "sensor_data",
        "sensor_id": sensor.sensor_id,
        "sensor_name": sensor.sensor_code,
        "sensor_type": sensor.sensor_type,
        "facility_id": sensor.equipment.facility_id,
        "equipment_id": sensor.equipment_id,
        "value": value,
        "measurement_unit": sensor.unit or "",
        "status": normalized_status,
        "alert_level": evaluation.alert_level,
        "timestamp": measured_at.astimezone(UTC).isoformat().replace("+00:00", "Z"),
    }


def generate_sensor_value(sensor_type: str, *, sensor_key: str | int | None = None) -> float:
    sensor_kind = sensor_type.strip().lower()
    roll = random.random()

    if sensor_kind == "temperature":
        if roll < 0.75:
            return round(sensor_degradation_service.apply(sensor_type, random.uniform(18, 25), sensor_key=sensor_key), 1)
        if roll < 0.93:
            return round(sensor_degradation_service.apply(sensor_type, random.uniform(26, 35), sensor_key=sensor_key), 1)
        return round(sensor_degradation_service.apply(sensor_type, random.uniform(36, 45), sensor_key=sensor_key), 1)

    if sensor_kind == "humidity":
        if roll < 0.75:
            return round(sensor_degradation_service.apply(sensor_type, random.uniform(40, 60), sensor_key=sensor_key), 1)
        if roll < 0.93:
            return round(sensor_degradation_service.apply(sensor_type, random.uniform(61, 75), sensor_key=sensor_key), 1)
        return round(sensor_degradation_service.apply(sensor_type, random.uniform(76, 90), sensor_key=sensor_key), 1)

    if sensor_kind == "voltage":
        if roll < 0.75:
            return round(sensor_degradation_service.apply(sensor_type, random.uniform(210, 230), sensor_key=sensor_key), 1)
        if roll < 0.93:
            return round(
                sensor_degradation_service.apply(
                    sensor_type,
                    random.choice([random.uniform(190, 209), random.uniform(231, 245)]),
                    sensor_key=sensor_key,
                ),
                1,
            )
        return round(
            sensor_degradation_service.apply(
                sensor_type,
                random.choice([random.uniform(160, 189), random.uniform(246, 270)]),
                sensor_key=sensor_key,
            ),
            1,
        )

    if sensor_kind == "pressure":
        if roll < 0.75:
            return round(sensor_degradation_service.apply(sensor_type, random.uniform(1.8, 2.5), sensor_key=sensor_key), 2)
        if roll < 0.93:
            return round(sensor_degradation_service.apply(sensor_type, random.uniform(2.6, 3.0), sensor_key=sensor_key), 2)
        return round(sensor_degradation_service.apply(sensor_type, random.uniform(3.1, 4.0), sensor_key=sensor_key), 2)

    return round(sensor_degradation_service.apply(sensor_type, random.uniform(0, 100), sensor_key=sensor_key), 2)


class SensorSimulatorService:
    def __init__(self) -> None:
        self._task: asyncio.Task | None = None
        self._stop_event = asyncio.Event()

    @property
    def is_running(self) -> bool:
        return self._task is not None and not self._task.done()

    async def start(self) -> tuple[bool, str]:
        if self.is_running:
            return False, "simulator is already running"
        self._stop_event.clear()
        self._task = asyncio.create_task(self._run_loop(), name="sensor-simulator")
        return True, "simulator started"

    async def stop(self) -> tuple[bool, str]:
        if not self.is_running:
            return False, "simulator is not running"
        self._stop_event.set()
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._task = None
        return True, "simulator stopped"

    async def _run_loop(self) -> None:
        try:
            while not self._stop_event.is_set():
                with SessionLocal() as db:
                    sensors = (
                        db.query(Sensor)
                        .options(joinedload(Sensor.equipment))
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
                    if sensors:
                        for sensor in sensors:
                            value = generate_sensor_value(sensor.sensor_type, sensor_key=sensor.sensor_id)
                            evaluation = evaluate_sensor_value(sensor.sensor_type, value)
                            measured_at = datetime.now(UTC)
                            data_row = SensorData(
                                sensor_id=sensor.sensor_id,
                                value=value,
                                status=evaluation.db_status,
                                measured_at=measured_at,
                                meta=json.dumps(
                                    {
                                        "status": evaluation.status,
                                        "alert_level": evaluation.alert_level,
                                        "source": "simulator",
                                    }
                                ),
                            )
                            db.add(data_row)
                            db.flush()

                            event = build_sensor_event(
                                sensor=sensor,
                                value=value,
                                evaluation=evaluation,
                                measured_at=measured_at,
                            )
                            await sensor_stream_service.broadcast_json(event)
                        db.commit()

                await asyncio.sleep(random.uniform(2.0, 3.0))
        except asyncio.CancelledError:
            raise
        finally:
            self._task = None


sensor_simulator_service = SensorSimulatorService()
