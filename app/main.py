import uvicorn

from fastapi import FastAPI, HTTPException, status
from uuid import uuid4, UUID

from models.jobs import JobsPayload, JobsResponse
from storage.jobs import jobs_db
from handlers.registry import handlers
from services.job_service import run_job


app = FastAPI()


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
def create_job(body: JobsPayload) -> JobsResponse:

    if body.type not in handlers:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "status": "failure",
                "message": f"Unsupported job type: '{body.type}'",
            },
        )

    job = JobsResponse(
        id=uuid4(),
        type=body.type,
        status="created",
        payload=body.payload,
    )

    jobs_db[job.id] = job

    return job


# GET ALL JOBS
@app.get("/jobs", response_model=list[JobsResponse])
def list_jobs() -> list[JobsResponse]:

    return list(jobs_db.values())


# GET ONE JOB
@app.get("/jobs/{job_id}", response_model=JobsResponse)
def get_job(job_id: UUID) -> JobsResponse:

    job = jobs_db.get(job_id)

    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "status": "failure",
                "message": f"Job not found: '{job_id}'",
            },
        )

    return job


# RUN JOB
@app.post(
    "/jobs/{job_id}/run",
    response_model=JobsResponse,
)
def run_job_endpoint(job_id: UUID) -> JobsResponse:

    return run_job(job_id)


if __name__ == "__main__":
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=8000,
    )