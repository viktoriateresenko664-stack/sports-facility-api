from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.employee import Employee
    from app.models.engineer_task import EngineerTask


class EngineerReport(Base):
    __tablename__ = "engineer_reports"
    __table_args__ = (UniqueConstraint("task_id", name="uq_engineer_reports_task_id"),)

    report_id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("engineer_tasks.task_id", ondelete="CASCADE"), nullable=False)
    engineer_id: Mapped[int] = mapped_column(ForeignKey("employees.employee_id", ondelete="RESTRICT"), nullable=False, index=True)
    report_text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    task: Mapped[EngineerTask] = relationship("EngineerTask", back_populates="report")
    engineer: Mapped[Employee] = relationship("Employee")
