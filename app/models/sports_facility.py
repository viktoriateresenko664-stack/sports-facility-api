from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Date, DateTime, Float, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import FacilityStatus
from sqlalchemy import Enum as SQLEnum

if TYPE_CHECKING:
    from app.models.engineer_task import EngineerTask
    from app.models.equipment import Equipment
    from app.models.user_request import UserRequest


class SportsFacility(Base):
    __tablename__ = "sports_facilities"

    facility_id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    facility_type: Mapped[str] = mapped_column(String(100), nullable=False)
    address: Mapped[str] = mapped_column(String(255), nullable=False)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    opening_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[FacilityStatus] = mapped_column(
        SQLEnum(FacilityStatus, name="facility_status", native_enum=True),
        default=FacilityStatus.ACTIVE,
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    equipment_items: Mapped[list[Equipment]] = relationship("Equipment", back_populates="facility")
    user_requests: Mapped[list[UserRequest]] = relationship("UserRequest", back_populates="facility")
    engineer_tasks: Mapped[list[EngineerTask]] = relationship("EngineerTask", back_populates="facility")
