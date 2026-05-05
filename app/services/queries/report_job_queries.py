from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import AuthPrincipal
from app.schemas.background_job import ReportJobStatusResponse
from app.services.background_job_service import BackgroundJobService


class ReportJobQueryService:
    @staticmethod
    def get_report_job_status(
        db: Session,
        *,
        job_id: UUID,
        principal: AuthPrincipal,
        job_service: BackgroundJobService,
        assert_job_access,
        to_response,
    ) -> ReportJobStatusResponse:
        job = job_service.get_job(db, job_id)
        if not job:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
        assert_job_access(principal, job)
        return to_response(job)
