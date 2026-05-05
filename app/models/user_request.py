from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import RequestStatus

if TYPE_CHECKING:
    from app.models.engineer_task import EngineerTask
    from app.models.sports_facility import SportsFacility
    from app.models.user import User


class UserRequest(Base):
    __tablename__ = "user_requests"

    request_id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, index=True)
    facility_id: Mapped[int] = mapped_column(ForeignKey("sports_facilities.facility_id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[RequestStatus] = mapped_column(
        SQLEnum(RequestStatus, name="request_status", native_enum=True),
        default=RequestStatus.CREATED,
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    owner: Mapped[User] = relationship("User", back_populates="requests")
    facility: Mapped[SportsFacility] = relationship("SportsFacility", back_populates="user_requests")
    engineer_task: Mapped[EngineerTask | None] = relationship("EngineerTask", back_populates="request", uselist=False)
