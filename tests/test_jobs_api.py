from fastapi.testclient import TestClient
from cache.redis import redis_client
from main import app
from uuid import UUID
from database.connection import SessionLocal
from repositories.job_repository import JobRepository
from queues.queue import JobQueue
from services.job_service import run_job
from database.models import JobStatus

client = TestClient(app)

def test_create_job_success():
    response = client.post("/jobs", json={
        "type": "echo",
        "payload": {"message": "Test Hello"}
    })
    assert response.status_code == 200
    assert response.json()["type"] == "echo"

def test_create_job_invalid_payload():
    response = client.post("/jobs", json={
        "type": "add",
        "payload": {
            "a": "a",
            "b": "b"
        }
    })
    assert response.status_code == 422

def test_create_job_unsupported_type():
    response = client.post("/jobs", json={
        "type": "bleh",
        "payload": {"message": "Test Hello"}
    })
    assert response.status_code == 400

def test_get_all_jobs():
    response = client.get("/jobs")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
    
def test_get_job_by_id_not_found():
    response = client.get("/jobs/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404

def test_run_job_lifecycle():
    response = client.post("/jobs", json={
        "type": "echo",
        "payload": {"message": "Test Hello"}
    })

    job_id = response.json()["id"]
    run_response = client.post(f"/jobs/{job_id}/run")
    assert run_response.status_code == 202
    assert run_response.json()["status"] == "queued"
    assert run_response.json()["result"] is None

def test_get_jobs_by_type():
    response = client.get("/jobs?type=echo")
    assert response.status_code == 200
    assert response.json()[0]["type"] == "echo"

def test_get_jobs_by_invalid_type():
    response = client.get("/jobs?type=bleh")
    assert response.status_code == 400

def test_get_jobs_by_status():
    response = client.get("/jobs?status=created")
    assert response.status_code == 200
    assert response.json()[0]["status"] == "created"

def test_get_jobs_by_invalid_status():
    response = client.get("/jobs?status=bleh")
    assert response.status_code == 422
    
def test_get_jobs_by_invalid_limit():
    response = client.get("/jobs?limit=abc")
    assert response.status_code == 422
    
def test_get_job_caches_in_redis():
    response = client.post("/jobs", json={
        "type": "echo",
        "payload": {"message": "Test Hello"}
    })
    job_id = response.json()["id"]
    get_response = client.get(f"/jobs/{job_id}")
    assert get_response.status_code == 200
    cached = redis_client.get(f"job:{job_id}")
    assert cached is not None

def test_worker_processes_queued_job():
    # 0. Clean the queue for a fresh test
    redis_client.delete("job:queue")
    # 1. Create the job
    response = client.post("/jobs", json={
        "type": "echo",
        "payload": {"message": "Test Hello"}
    })
    job_id = response.json()["id"]
    # 2. Enqueue the job (Producer)
    run_response = client.post(f"/jobs/{job_id}/run")
    assert run_response.status_code == 202
    assert run_response.json()["status"] == "queued"
    # 3. Simulate Worker picking up and running the job (Consumer)
    queue = JobQueue()
    dequeued_id = queue.dequeue(timeout=1)
    assert dequeued_id is not None
    assert dequeued_id == UUID(job_id)
    db = SessionLocal()
    try:
        repo = JobRepository(db)
        run_job(dequeued_id, repo)
    finally:
        db.close()
    # 4. Verify via GET /jobs/{id} that the job is now COMPLETED!
    get_response = client.get(f"/jobs/{job_id}")
    assert get_response.status_code == 200
    assert get_response.json()["status"] == "completed"
    assert get_response.json()["result"] == {"message": "Test Hello"}

def test_job_failure_moves_to_dlq():
    # 0. Clean the queues
    redis_client.delete("job:queue")
    redis_client.delete("job:dlq")

    # 1. Create a job that will fail (Division by zero!)
    response = client.post("/jobs", json={
        "type": "division",
        "payload": {"a": 10, "b": 0}
    })
    job_id = response.json()["id"]

    # 2. Set max_retries = 1 directly in DB so the test runs fast!
    db = SessionLocal()
    repo = JobRepository(db)
    job = repo.get_job_by_id(UUID(job_id))
    assert job is not None
    job.max_retries = 1
    repo.update(job)
    db.close()

    # 3. Enqueue the job (Producer)
    client.post(f"/jobs/{job_id}/run")

    # 4. First Execution (Attempt 1 -> Fails -> Retried & Re-enqueued)
    queue = JobQueue()
    dequeued_id = queue.dequeue(timeout=1)
    assert dequeued_id == UUID(job_id)
    assert dequeued_id is not None

    db = SessionLocal()
    repo = JobRepository(db)
    job = run_job(dequeued_id, repo)
    assert job.status == JobStatus.FAILED
    assert job.error_message is not None

    # Simulate worker retry decision (Attempt 1 < max_retries 1):
    job.retry_count += 1
    job.status = JobStatus.QUEUED
    repo.update(job)
    queue.enqueue(job.id)
    db.close()

    # 5. Second Execution (Attempt 2 -> Exceeds max_retries -> Moves to DLQ!)
    dequeued_id_2 = queue.dequeue(timeout=1)
    assert dequeued_id_2 == UUID(job_id)
    assert dequeued_id_2 is not None

    db = SessionLocal()
    repo = JobRepository(db)
    job_2 = run_job(dequeued_id_2, repo)
    # retry_count is 1, max_retries is 1 -> Exhausted!
    job_2.status = JobStatus.FAILED
    repo.update(job_2)
    queue.enqueue_dlq(job_2.id)
    db.close()

    # 6. VERIFY: The job is now in the Dead Letter Queue!
    dlq_jobs = queue.get_dlq_jobs()
    assert UUID(job_id) in dlq_jobs

