from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.background_job import BackgroundJob
from app.models.enums import AccountType, BackgroundJobStatus
from app.repositories.background_job_repository import BackgroundJobRepository


class BackgroundJobService:
    def __init__(self) -> None:
        self.repo = BackgroundJobRepository()

    def create_job(
        self,
        db: Session,
        *,
        owner_id: int,
        owner_type: AccountType,
        task_id: int | None = None,
        task_name: str,
        payload: dict[str, Any] | None = None,
    ) -> BackgroundJob:
        job = BackgroundJob(
            owner_id=owner_id,
            owner_type=owner_type,
            task_id=task_id,
            task_name=task_name,
            status=BackgroundJobStatus.PENDING,
            payload=payload,
        )
        self.repo.create(db, job)
        return job

    def get_job(self, db: Session, job_id: UUID) -> BackgroundJob | None:
        return self.repo.get_by_id(db, job_id)

    def mark_processing(self, db: Session, job: BackgroundJob) -> BackgroundJob:
        job.status = BackgroundJobStatus.PROCESSING
        job.started_at = datetime.now(UTC)
        return self.repo.update(db, job)

    def mark_success(self, db: Session, job: BackgroundJob, result: dict[str, Any] | None = None) -> BackgroundJob:
        job.status = BackgroundJobStatus.SUCCESS
        job.result = result
        job.finished_at = datetime.now(UTC)
        return self.repo.update(db, job)

    def mark_failed(self, db: Session, job: BackgroundJob, error: str) -> BackgroundJob:
        job.status = BackgroundJobStatus.FAILED
        job.error = error
        job.finished_at = datetime.now(UTC)
        return self.repo.update(db, job)
