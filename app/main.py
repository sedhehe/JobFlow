from typing import Annotated
import uvicorn

from fastapi import FastAPI, HTTPException, status, Depends, Query
from uuid import uuid4, UUID

from models.jobs import JobsPayload, JobsResponse
from handlers.registry import handlers
from services.job_service import run_job

from sqlalchemy.orm import Session
from repositories.job_repository import JobRepository
from database.models import Job, JobStatus
from database.connection import get_db

from cache.redis import JobCache

app = FastAPI()

def get_job_repo(db: Session = Depends(get_db)) -> JobRepository:
    return JobRepository(db)

JobRepo = Annotated[JobRepository, Depends(get_job_repo)]

def get_job_cache():
    return JobCache()

JobCacheDep = Annotated[JobCache, Depends(get_job_cache)]

@app.get("/")
def hello():
    return {"message": "JobFlow API"}


# CREATE JOB
@app.post(
    "/jobs",
    response_model=JobsResponse,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "description": "Unsupported job type"
        }
    },
)
def create_job(body: JobsPayload, repo: JobRepo) -> Job:

    handler = handlers.get(body.type)
    if handler is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "status": "failure",
                "message": f"Unsupported job type: '{body.type}'",
            },
        )

    try:
        validated_payload = handler.payload_schema.model_validate(body.payload)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={
                "status": "failure",
                "message": f"Invalid payload for job type '{body.type}': {str(e)}",
            },
        )

    job = Job(
        id=uuid4(),
        type=body.type,
        status=JobStatus.CREATED,
        payload=validated_payload.model_dump(),
    )

    repo.create(job)

    return job


# GET ALL JOBS
@app.get("/jobs", response_model=list[JobsResponse])
def list_jobs(repo: JobRepo,
limit: int = Query(default = 10, ge = 1, le = 100),
job_status: JobStatus | None = Query(default = None, alias = "status"),
type: str | None = None,
offset: int = Query(default = 0, ge = 0)) -> list[Job]:

    if type is not None and type not in handlers:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "status": "failure",
                "message": f"Invalid job type: '{type}'",
            },
        )
    if job_status is not None and job_status not in JobStatus:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "status": "failure",
                "message": f"Invalid job status: '{job_status}'",
            },
        )
    
    jobs = repo.get_all_jobs(
        limit = limit,
        status = job_status,
        type = type,
        offset = offset)

    return list(jobs)


# GET ONE JOB
@app.get("/jobs/{job_id}", response_model=JobsResponse)
def get_job(job_id: UUID, repo: JobRepo, cache: JobCacheDep) -> Job | dict:

    job = cache.get(job_id)
    if job is  None:

        job = repo.get_job_by_id(job_id)

        if job is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "status": "failure",
                    "message": f"Job not found: '{job_id}'",
                },
            )

        cache.set(job)

    return job


# RUN JOB
@app.post(
    "/jobs/{job_id}/run",
    response_model=JobsResponse,
)
def run_job_endpoint(job_id: UUID, repo: JobRepo, cache: JobCacheDep) -> Job:

    updated_job = run_job(job_id, repo)

    cache.delete(job_id)
    
    return updated_job


if __name__ == "__main__":
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=8000,
    )