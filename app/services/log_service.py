from typing import Any

from sqlalchemy.orm import Session

from app.models.enums import LogStatus
from app.models.system_action_log import SystemActionLog


class LogService:
    @staticmethod
    def log_action(
        db: Session,
        *,
        action_type: str,
        entity_type: str,
        entity_id: str,
        status: LogStatus,
        actor_user_id: int | None = None,
        actor_employee_id: int | None = None,
        user_role: str | None = None,
        details: dict[str, Any] | None = None,
        message: str | None = None,
    ) -> None:
        if (actor_user_id is None and actor_employee_id is None) or (
            actor_user_id is not None and actor_employee_id is not None
        ):
            return
        log = SystemActionLog(
            actor_user_id=actor_user_id,
            actor_employee_id=actor_employee_id,
            user_role=user_role,
            action_type=action_type,
            entity_type=entity_type,
            entity_id=entity_id,
            status=status,
            details=details,
            message=message,
        )
        db.add(log)
