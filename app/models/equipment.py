from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import EquipmentStatus

if TYPE_CHECKING:
    from app.models.sensor import Sensor
    from app.models.sports_facility import SportsFacility


class Equipment(Base):
    __tablename__ = "equipment"

    equipment_id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    facility_id: Mapped[int] = mapped_column(ForeignKey("sports_facilities.facility_id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    equipment_type: Mapped[str] = mapped_column(String(100), nullable=False)
    serial_number: Mapped[str | None] = mapped_column(String(120), nullable=True)
    status: Mapped[EquipmentStatus] = mapped_column(
        SQLEnum(EquipmentStatus, name="equipment_status", native_enum=True),
        default=EquipmentStatus.ACTIVE,
        nullable=False,
        index=True,
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    facility: Mapped[SportsFacility] = relationship("SportsFacility", back_populates="equipment_items")
    sensors: Mapped[list[Sensor]] = relationship("Sensor", back_populates="equipment")
