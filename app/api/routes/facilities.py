from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import and_, func
from sqlalchemy.orm import Session, joinedload

from app.api.deps import require_roles
from app.db.session import get_db
from app.models.equipment import Equipment
from app.models.sensor import Sensor
from app.models.sensor_data import SensorData
from app.models.sports_facility import SportsFacility

router = APIRouter(prefix="/facilities", tags=["facilities"])


def _latest_sensor_data_map(db: Session, facility_id: int) -> dict[int, SensorData]:
    latest_subquery = (
        db.query(
            SensorData.sensor_id.label("sensor_id"),
            func.max(SensorData.measured_at).label("latest_at"),
        )
        .join(Sensor, Sensor.sensor_id == SensorData.sensor_id)
        .join(Equipment, Equipment.equipment_id == Sensor.equipment_id)
        .filter(Equipment.facility_id == facility_id)
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


@router.get(
    "/{facility_id}/details",
    summary="Get Facility Details",
    description="Returns facility card data with equipment and sensor readings for desktop objects page.",
)
def get_facility_details(
    facility_id: int,
    db: Session = Depends(get_db),
    _=Depends(require_roles("ENGINEER", "OPERATOR", "CHIEF_ENGINEER", "ADMIN")),
) -> dict:
    facility = (
        db.query(SportsFacility)
        .options(
            joinedload(SportsFacility.equipment_items).joinedload(Equipment.sensors),
        )
        .filter(SportsFacility.facility_id == facility_id)
        .first()
    )
    if not facility:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Facility not found")

    latest_data_by_sensor = _latest_sensor_data_map(db, facility_id)

    equipment_payload: list[dict] = []
    sensors_payload: list[dict] = []

    for equipment in facility.equipment_items:
        equipment_payload.append(
            {
                "equipment_id": equipment.equipment_id,
                "name": equipment.name,
                "type": equipment.equipment_type,
                "status": equipment.status.value if hasattr(equipment.status, "value") else str(equipment.status),
                "serial_number": equipment.serial_number,
                "description": equipment.description,
            }
        )

        for sensor in equipment.sensors:
            latest = latest_data_by_sensor.get(sensor.sensor_id)
            sensors_payload.append(
                {
                    "sensor_id": sensor.sensor_id,
                    "equipment_id": equipment.equipment_id,
                    "name": sensor.sensor_code,
                    "type": sensor.sensor_type,
                    "unit": sensor.unit or "",
                    "status": sensor.status.value if hasattr(sensor.status, "value") else str(sensor.status),
                    "value": float(latest.value) if latest else None,
                    "measured_at": latest.measured_at.isoformat().replace("+00:00", "Z") if latest else None,
                    "alert_status": latest.status.value if latest and hasattr(latest.status, "value") else None,
                }
            )

    return {
        "facility_id": facility.facility_id,
        "name": facility.name,
        "status": facility.status.value if hasattr(facility.status, "value") else str(facility.status),
        "address": facility.address,
        "latitude": facility.latitude,
        "longitude": facility.longitude,
        "type": facility.facility_type,
        "description": facility.description,
        "equipment": equipment_payload,
        "sensors": sensors_payload,
    }
