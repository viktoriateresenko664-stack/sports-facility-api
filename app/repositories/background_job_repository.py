from uuid import UUID

from sqlalchemy.orm import Session

from app.models.background_job import BackgroundJob


class BackgroundJobRepository:
    def create(self, db: Session, job: BackgroundJob) -> BackgroundJob:
        db.add(job)
        db.flush()
        return job

    def get_by_uuid(self, db: Session, job_id: UUID) -> BackgroundJob | None:
        return db.get(BackgroundJob, job_id)

    def update(self, db: Session, job: BackgroundJob) -> BackgroundJob:
        db.add(job)
        db.flush()
        return job
