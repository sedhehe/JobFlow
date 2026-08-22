from uuid import UUID

from fastapi import HTTPException, status

from models.jobs import JobsResponse
from storage.jobs import jobs_db
from handlers.registry import handlers


def run_job(job_id: UUID) -> JobsResponse:

    # 1. Find the job
    job = jobs_db.get(job_id)

    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "status": "failure",
                "message": f"Job not found: '{job_id}'",
            },
        )

    # 2. Check whether it can be executed
    if job.status != "created":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "status": "failure",
                "message": f"Job cannot be run from '{job.status}' state",
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

    # 4. Actually execute the job
    result = handler.execute(job.payload)

    # 5. Update job
    updated_job = JobsResponse(
        id=job.id,
        type=job.type,
        status="completed",
        payload=job.payload,
        result=result,
    )

    # 6. Store updated job
    jobs_db[job.id] = updated_job

    # 7. Return it
    return updated_job