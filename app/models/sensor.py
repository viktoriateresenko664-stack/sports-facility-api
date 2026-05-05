from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import SensorStatus

if TYPE_CHECKING:
    from app.models.equipment import Equipment
    from app.models.sensor_data import SensorData


class Sensor(Base):
    __tablename__ = "sensors"

    sensor_id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    equipment_id: Mapped[int] = mapped_column(ForeignKey("equipment.equipment_id", ondelete="CASCADE"), nullable=False, index=True)
    sensor_code: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    sensor_type: Mapped[str] = mapped_column(String(100), nullable=False)
    unit: Mapped[str | None] = mapped_column(String(50), nullable=True)
    status: Mapped[SensorStatus] = mapped_column(
        SQLEnum(SensorStatus, name="sensor_status", native_enum=True),
        default=SensorStatus.ACTIVE,
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    equipment: Mapped[Equipment] = relationship("Equipment", back_populates="sensors")
    data_points: Mapped[list[SensorData]] = relationship("SensorData", back_populates="sensor")
