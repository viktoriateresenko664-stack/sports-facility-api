from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, Text, UniqueConstraint, func
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import TaskStatus

if TYPE_CHECKING:
    from app.models.employee import Employee
    from app.models.engineer_report import EngineerReport
    from app.models.sports_facility import SportsFacility
    from app.models.user_request import UserRequest


class EngineerTask(Base):
    __tablename__ = "engineer_tasks"
    __table_args__ = (UniqueConstraint("request_id", name="uq_engineer_tasks_request_id"),)

    task_id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    facility_id: Mapped[int] = mapped_column(ForeignKey("sports_facilities.facility_id", ondelete="CASCADE"), nullable=False, index=True)
    request_id: Mapped[int | None] = mapped_column(ForeignKey("user_requests.request_id", ondelete="SET NULL"), nullable=True)
    created_by_employee_id: Mapped[int] = mapped_column(ForeignKey("employees.employee_id", ondelete="RESTRICT"), nullable=False, index=True)
    assigned_engineer_id: Mapped[int] = mapped_column(ForeignKey("employees.employee_id", ondelete="RESTRICT"), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    operator_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[TaskStatus] = mapped_column(
        SQLEnum(TaskStatus, name="task_status", native_enum=True),
        default=TaskStatus.CREATED,
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    facility: Mapped[SportsFacility] = relationship("SportsFacility", back_populates="engineer_tasks")
    request: Mapped[UserRequest | None] = relationship("UserRequest", back_populates="engineer_task")
    created_by_employee: Mapped[Employee] = relationship(
        "Employee", back_populates="created_tasks", foreign_keys=[created_by_employee_id]
    )
    assigned_engineer: Mapped[Employee] = relationship(
        "Employee", back_populates="assigned_tasks", foreign_keys=[assigned_engineer_id]
    )
    report: Mapped[EngineerReport | None] = relationship("EngineerReport", back_populates="task", uselist=False)
