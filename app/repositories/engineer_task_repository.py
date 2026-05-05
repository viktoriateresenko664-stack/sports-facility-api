from sqlalchemy.orm import Session
from sqlalchemy.orm import selectinload

from app.models.engineer_task import EngineerTask


class EngineerTaskRepository:
    def create(self, db: Session, task: EngineerTask) -> EngineerTask:
        db.add(task)
        db.flush()
        return task

    def save(self, db: Session, task: EngineerTask) -> EngineerTask:
        db.add(task)
        db.commit()
        db.refresh(task)
        return task

    def get_by_id(self, db: Session, task_id: int) -> EngineerTask | None:
        return (
            db.query(EngineerTask)
            .options(
                selectinload(EngineerTask.facility),
                selectinload(EngineerTask.assigned_engineer),
                selectinload(EngineerTask.request),
            )
            .filter(EngineerTask.task_id == task_id)
            .first()
        )

    def list_all(self, db: Session) -> list[EngineerTask]:
        return (
            db.query(EngineerTask)
            .options(
                selectinload(EngineerTask.facility),
                selectinload(EngineerTask.assigned_engineer),
                selectinload(EngineerTask.request),
            )
            .order_by(EngineerTask.created_at.desc())
            .all()
        )
