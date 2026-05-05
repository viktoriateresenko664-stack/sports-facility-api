from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import LogStatus


class SystemActionLog(Base):
    __tablename__ = "system_action_log"
    __table_args__ = (
        CheckConstraint(
            "(actor_user_id IS NOT NULL AND actor_employee_id IS NULL) OR "
            "(actor_user_id IS NULL AND actor_employee_id IS NOT NULL)",
            name="ck_system_action_log_single_actor",
        ),
    )

    log_id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    actor_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True, index=True)
    actor_employee_id: Mapped[int | None] = mapped_column(ForeignKey("employees.employee_id", ondelete="SET NULL"), nullable=True, index=True)
    user_role: Mapped[str | None] = mapped_column(String(120), nullable=True)
    action_type: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    entity_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    status: Mapped[LogStatus] = mapped_column(
        SQLEnum(LogStatus, name="log_status", native_enum=True),
        nullable=False,
        index=True,
    )
    details: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
