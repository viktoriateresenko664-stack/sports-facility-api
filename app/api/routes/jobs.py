from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import AuthPrincipal, get_current_principal, require_roles
from app.db.session import get_db
from app.models.enums import AccountType
from app.schemas.background_job import BackgroundJobResponse
from app.services.background_job_service import BackgroundJobService

router = APIRouter(prefix="/jobs", tags=["jobs"])
service = BackgroundJobService()
JOB_RESPONSES = {
    400: {"description": "Bad Request"},
    401: {"description": "Unauthorized"},
    403: {"description": "Forbidden"},
    404: {"description": "Not Found"},
    409: {"description": "Conflict"},
}


@router.get(
    "/{job_id}",
    response_model=BackgroundJobResponse,
    responses=JOB_RESPONSES,
    summary="Get Background Job",
    description="Returns status and result metadata for a background job by its ID.",
)
def get_job(
    job_id: UUID,
    db: Session = Depends(get_db),
    principal: AuthPrincipal = Depends(get_current_principal),
    _=Depends(require_roles("ENGINEER", "OPERATOR", "CHIEF_ENGINEER", "ADMIN", "USER")),
) -> BackgroundJobResponse:
    job = service.get_job(db, job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    is_admin = "ADMIN" in principal.roles
    if not is_admin:
        if principal.account_type == AccountType.USER:
            if not (job.owner_type == AccountType.USER and job.owner_id == principal.subject_id):
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
        elif principal.account_type == AccountType.EMPLOYEE:
            if not (job.owner_type == AccountType.EMPLOYEE and job.owner_id == principal.subject_id):
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
        else:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    return BackgroundJobResponse.model_validate(job)
