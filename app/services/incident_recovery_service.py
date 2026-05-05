from __future__ import annotations

import json
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models.equipment import Equipment
from app.models.enums import EquipmentStatus, FacilityStatus, SensorDataStatus, SensorStatus
from app.models.sensor import Sensor
from app.models.sensor_data import SensorData
from app.models.sports_facility import SportsFacility
from app.services.sensor_degradation_service import sensor_degradation_service


class IncidentRecoveryService:
    _NORMAL_VALUES_BY_SENSOR_TYPE: dict[str, float] = {
        "temperature": 22.0,
        "humidity": 50.0,
        "voltage": 220.0,
        "pressure": 2.2,
    }

    @classmethod
    def _normal_value(cls, sensor_type: str) -> float:
        key = (sensor_type or "").strip().lower()
        return cls._NORMAL_VALUES_BY_SENSOR_TYPE.get(key, 0.0)

    @classmethod
    def normalize_facility_sensors(
        cls,
        db: Session,
        *,
        facility_id: int,
        source: str,
        task_id: int | None = None,
    ) -> dict[str, int]:
        sensors = (
            db.query(Sensor)
            .join(Equipment, Equipment.equipment_id == Sensor.equipment_id)
            .filter(Equipment.facility_id == facility_id)
            .all()
        )
        if not sensors:
            return {"normalized_sensors": 0, "normalized_equipment": 0, "facility_updated": 0}

        equipment_ids = {sensor.equipment_id for sensor in sensors}
        measured_at = datetime.now(UTC)

        for sensor in sensors:
            sensor.status = SensorStatus.ACTIVE
            db.add(sensor)
            row = SensorData(
                sensor_id=sensor.sensor_id,
                value=cls._normal_value(sensor.sensor_type),
                status=SensorDataStatus.NORMAL,
                measured_at=measured_at,
                meta=json.dumps(
                    {
                        "status": "NORMAL",
                        "alert_level": 0,
                        "source": source,
                        "task_id": task_id,
                    }
                ),
            )
            db.add(row)

        equipment_rows = db.query(Equipment).filter(Equipment.equipment_id.in_(equipment_ids)).all()
        for equipment in equipment_rows:
            equipment.status = EquipmentStatus.ACTIVE
            db.add(equipment)

        facility = db.get(SportsFacility, facility_id)
        facility_updated = 0
        if facility is not None:
            facility.status = FacilityStatus.ACTIVE
            db.add(facility)
            facility_updated = 1

        # Stop active degradation and begin smooth recovery curve for generators/simulators.
        sensor_degradation_service.start_recovery()
        # In fake-only mode keep exactly one active incident:
        # once one incident is resolved, rotate critical state to another sensor.
        sensor_degradation_service.mark_incident_resolved(facility_id=facility_id)

        return {
            "normalized_sensors": len(sensors),
            "normalized_equipment": len(equipment_rows),
            "facility_updated": facility_updated,
        }


incident_recovery_service = IncidentRecoveryService()
