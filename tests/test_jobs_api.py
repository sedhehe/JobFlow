from fastapi.testclient import TestClient
from cache.redis import redis_client
from main import app

client = TestClient(app)

def test_create_job_success():
    response = client.post("/jobs", json={
        "type": "echo",
        "payload": {"message": "Hello"}
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
        "payload": {"message": "Hello"}
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
        "payload": {"message": "Hello"}
    })

    job_id = response.json()["id"]
    run_response = client.post(f"/jobs/{job_id}/run")
    assert run_response.status_code == 200
    assert run_response.json()["status"] == "completed"
    assert run_response.json()["result"] == {"message": "Hello"}

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
        "payload": {"message": "Hello"}
    })
    job_id = response.json()["id"]
    get_response = client.get(f"/jobs/{job_id}")
    assert get_response.status_code == 200
    cached = redis_client.get(f"job:{job_id}")
    assert cached is not None

def test_run_job_invalidates_cache():
    response = client.post("/jobs", json={
        "type": "echo",
        "payload": {"message": "Hello"}
    })
    job_id = response.json()["id"]
    run_response = client.post(f"/jobs/{job_id}/run")
    assert run_response.status_code == 200
    cached = redis_client.get(f"job:{job_id}")
    assert cached is None