from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Float, ForeignKey, Integer, Text, func
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import SensorDataStatus

if TYPE_CHECKING:
    from app.models.sensor import Sensor


class SensorData(Base):
    __tablename__ = "sensor_data"

    data_id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    sensor_id: Mapped[int] = mapped_column(ForeignKey("sensors.sensor_id", ondelete="CASCADE"), nullable=False, index=True)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[SensorDataStatus] = mapped_column(
        SQLEnum(SensorDataStatus, name="sensor_data_status", native_enum=True),
        default=SensorDataStatus.NORMAL,
        nullable=False,
        index=True,
    )
    measured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    meta: Mapped[str | None] = mapped_column(Text, nullable=True)

    sensor: Mapped[Sensor] = relationship("Sensor", back_populates="data_points")
