from uuid import UUID

from fastapi import HTTPException, status

from models.jobs import JobsResponse
from repositories.job_repository import JobRepository
from database.models import JobStatus
from handlers.registry import handlers


def run_job(job_id: UUID, repo: JobRepository) -> JobsResponse:

    # 1. Find the job
    job = repo.get_job_by_id(job_id)

    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "status": "failure",
                "message": f"Job not found: '{job_id}'",
            },
        )

    # 2. Check whether it can be executed
    if job.status != JobStatus.CREATED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "status": "failure",
                "message": f"Job cannot be run from '{job.status.value}' state",
            },
        )

    # 3. Find the appropriate handler
    handler = handlers.get(job.type)

    if handler is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "status": "failure",
                "message": f"No handler registered for job type '{job.type}'",
            },
        )

    # 4. Parse stored dict into the handler's Pydantic model
    payload = handler.payload_schema(**job.payload)

    job.status = JobStatus.RUNNING
    repo.update(job)
    
    # 5. Actually execute the job
    try:
        result = handler.execute(payload)
        # 6. Update fields on the database model (Success)
        job.status = JobStatus.COMPLETED
        job.result = result
    except Exception as e:
        # 6. Update fields on the database model (Failure)
        job.status=JobStatus.FAILED
        job.result = {"error":str(e)}

    # 7. Persist changes to PostgreSQL & return
    updated_job = repo.update(job)
    return updated_job
