import uvicorn
from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel
from uuid import uuid4,UUID

app = FastAPI()

jobs_db = {}

class EchoPayload(BaseModel):
    message: str
class EchoHandler(BaseModel):
    def execute(self, message: str) -> dict:
        return {"message": message}
    
class AddPayload(BaseModel):
    a: int
    b: int
class AdditionHandler:
    def execute(self, a: int, b: int) -> dict:
        return {"sum": a + b}

# Create Jobs payloads' model
class JobsPayload(BaseModel):
    type: str
    payload: EchoPayload | AddPayload
class JobsResponse(BaseModel):
    id: UUID 
    type: str
    status: str
    payload: EchoPayload | AddPayload
    result: dict | None = None


@app.get("/")
def hello():
    return {"message": "JobFlow API"}

# create jobs
@app.post(
    "/jobs",
    response_model=JobsResponse,
    responses={status.HTTP_400_BAD_REQUEST: {"description": "Unsupported job type or invalid payload"}},
)
def jobs(body: JobsPayload) -> JobsResponse:
    if body.type == "echo":
        job = JobsResponse(
            id=uuid4(),
            type="echo",
            status="created",
            payload=EchoPayload(message=body.payload.message),
        )
    elif body.type == "add":
        job = JobsResponse(
            id=uuid4(),
            type="add",
            status="created",
            payload=AddPayload(a=body.payload.a, b=body.payload.b),
        )

    jobs_db[job.id] = job
    print(jobs_db)
    return job

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail={"status": "failure", "message": f"Unsupported job type: '{body.type}'"},
    )

# get all jobs
@app.get("/jobs", response_model=list[JobsResponse])
def list_jobs() -> list[JobsResponse]:
    return list(jobs_db.values())

# get job by it's id
@app.get("/jobs/{job_id}", response_model=JobsResponse)
def get_job(job_id: UUID) -> JobsResponse:
    job = jobs_db.get(job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"status": "failure", "message": f"Job not found: '{job_id}'"},
        )
    return job

@app.post("/jobs/{job_id}/run", response_model=JobsResponse)
def run_job(job_id: UUID) -> JobsResponse:
    job = jobs_db.get(job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"status": "failure", "message": f"Job not found: '{job_id}'"},
        )
    if job.status == "created":
        if job.type == "echo":
            result = JobsResponse(
                id = job.id,
                type = job.type,
                status = "completed",
                payload = job.payload,
                result = {"message": job.payload.message}    
            )
        elif job.type == "add":
            result = JobsResponse(
                id = job.id,
                type = job.type,
                status = "completed",
                payload = job.payload,
                result = {"sum": job.payload.a + job.payload.b}
            )
        jobs_db[job.id] = result
        print("job ran successfully")
        return result
    elif job.status == "completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"status": "failure", "message": f"Job has already completed"},
        )
    elif job.status == "failed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"status": "failure", "message": f"Job has failed"},
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"status": "failure", "message": f"Job not found"},
        )

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
    