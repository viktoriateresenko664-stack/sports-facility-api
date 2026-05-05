from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import AvailabilityStatus

if TYPE_CHECKING:
    from app.models.engineer_task import EngineerTask
    from app.models.role import EmployeeRole


class Employee(Base):
    __tablename__ = "employees"

    employee_id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    employee_key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    middle_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    position: Mapped[str] = mapped_column(String(120), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    availability_status: Mapped[AvailabilityStatus] = mapped_column(
        SQLEnum(AvailabilityStatus, name="availability_status", native_enum=True),
        default=AvailabilityStatus.AVAILABLE,
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    roles: Mapped[list[EmployeeRole]] = relationship("EmployeeRole", back_populates="employee", cascade="all, delete-orphan")
    created_tasks: Mapped[list[EngineerTask]] = relationship(
        "EngineerTask",
        back_populates="created_by_employee",
        foreign_keys="EngineerTask.created_by_employee_id",
    )
    assigned_tasks: Mapped[list[EngineerTask]] = relationship(
        "EngineerTask",
        back_populates="assigned_engineer",
        foreign_keys="EngineerTask.assigned_engineer_id",
    )
