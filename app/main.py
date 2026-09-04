from typing import Annotated
import uvicorn

from fastapi import FastAPI, HTTPException, status, Depends, Query, WebSocket, WebSocketDisconnect, Header, Request
from starlette.requests import HTTPConnection
from uuid import uuid4, UUID

from models.jobs import JobsPayload, JobsResponse
from handlers.registry import handlers
# from services.job_service import run_job
from services.idempotency import Idempotency

from sqlalchemy.orm import Session
from repositories.job_repository import JobRepository
from database.models import Job, JobStatus
from database.connection import get_db

from cache.redis import JobCache
from queues.queue import JobQueue

from tasks.job_tasks import execute_job_task

import asyncio
from contextlib import asynccontextmanager
from realtime.connection_manager import ConnectionManager
from realtime.pubsub import start_redis_listener, publish_job_event

from services.rate_limiter import RateLimiter

rate_limiter = RateLimiter()

def rate_limit(connection: HTTPConnection):
    client_ip = connection.headers.get("X-Forwarded-For", connection.client.host if connection.client else "127.0.0.1")

    if client_ip == "testclient" and "X-Forwarded-For" not in connection.headers:
        return

    allowed = rate_limiter.is_allowed(client_ip, capacity=10, refill_rate=1.0)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={"status": "failure", "message": "Rate limit exceeded. Try again later."},
            headers={"Retry-After": "1"}
        )

manager = ConnectionManager()

@asynccontextmanager
async def lifespan(app: FastAPI):
    listener = asyncio.create_task(start_redis_listener(manager))
    yield
    listener.cancel()

app = FastAPI(
    lifespan=lifespan,
    dependencies=[Depends(rate_limit)]
    )

def get_job_repo(db: Session = Depends(get_db)) -> JobRepository:
    return JobRepository(db)

JobRepo = Annotated[JobRepository, Depends(get_job_repo)]

def get_job_cache():
    return JobCache()

JobCacheDep = Annotated[JobCache, Depends(get_job_cache)]

def get_job_queue():
    return JobQueue()

JobQueueDep = Annotated[JobQueue, Depends(get_job_queue)]

idempotency = Idempotency()


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
def create_job(body: JobsPayload, repo: JobRepo, x_idempotency_key: str | None = Header(default=None)) -> Job | dict:

    if x_idempotency_key:
        status_key, cached_response = idempotency.check_or_lock(x_idempotency_key)
        if status_key == "IN_PROGRESS":
            raise HTTPException(
                status_code = status.HTTP_409_CONFLICT,
                detail={
                    "status": "failure",
                    "message": "Job is already in progress"
                }
            )
        if status_key == "COMPLETED" and cached_response:
            return cached_response
    

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

    if x_idempotency_key:
        response_data = JobsResponse.model_validate(job).model_dump(mode="json")
        idempotency.save_response(x_idempotency_key, response_data)

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
    if job is None:

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
    status_code=status.HTTP_202_ACCEPTED,
    response_model=JobsResponse,
    responses={
        status.HTTP_404_NOT_FOUND: {
            "description": "Job not found"
        }
    }
)
def run_job_endpoint(job_id: UUID, repo: JobRepo, cache: JobCacheDep, x_idempotency_key: str | None = Header(default=None)) -> Job | dict:

    if x_idempotency_key:
        status_key, cached_response = idempotency.check_or_lock(x_idempotency_key)
        if status_key == "IN_PROGRESS":
            raise HTTPException(
                status_code = status.HTTP_409_CONFLICT,
                detail={
                    "status": "failure",
                    "message": "Job is already in progress"
                }
            )
        if status_key == "COMPLETED" and cached_response:
            return cached_response

    job = repo.get_job_by_id(job_id)
    
    if job is None:
        raise HTTPException(
            status_code = status.HTTP_404_NOT_FOUND,
            detail = {
                "status": "failure",
                "message": f"Job not found: '{job_id}'",
            }
        )
    
    job.status = JobStatus.QUEUED
    repo.update(job)
    publish_job_event(job_id, {"status": "queued", "job_id": str(job_id)})

    cache.delete(job_id)

    handler = handlers.get(job.type)
    priority_queue = getattr(handler, "priority", "default")
    execute_job_task.apply_async(args=[str(job_id)], queue = priority_queue)

    if x_idempotency_key:
        response_data = JobsResponse.model_validate(job).model_dump(mode="json")
        idempotency.save_response(x_idempotency_key, response_data)

    return job

@app.websocket("/ws/jobs/{job_id}")
async def websocket_job_endpoint(websocket: WebSocket, job_id: UUID):
    await manager.connect(job_id, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await manager.disconnect(job_id, websocket)
    

if __name__ == "__main__":
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=8000,
    )