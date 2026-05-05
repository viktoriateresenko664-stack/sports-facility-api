from sqlalchemy.orm import Session

from app.models.system_action_log import SystemActionLog


class SystemActionLogRepository:
    def create(self, db: Session, log: SystemActionLog) -> SystemActionLog:
        db.add(log)
        db.flush()
        return log

    def get_by_id(self, db: Session, log_id: int) -> SystemActionLog | None:
        return db.get(SystemActionLog, log_id)