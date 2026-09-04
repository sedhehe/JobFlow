from fastapi.testclient import TestClient
from main import app
from tasks.job_tasks import execute_job_task

client = TestClient(app)

def test_websocket_receives_live_job_lifecycle():
    with TestClient(app) as client:
        # 1. Create the job
        response = client.post("/jobs", json={
            "type": "echo",
            "payload": {"message": "Realtime Hello"}
        })
        assert response.status_code == 200
        job_id = response.json()["id"]

        # 2. Connect to the WebSocket before running the job:
        with client.websocket_connect(f"/ws/jobs/{job_id}") as ws:
            
            # 3. Trigger the job (POST /jobs/{id}/run publishes {"status": "queued"})
            client.post(f"/jobs/{job_id}/run")
            
            event1 = ws.receive_json()
            assert event1["status"] == "queued"
            assert event1["job_id"] == job_id

            # 4. Execute the worker task (publishes "running" then "completed")
            execute_job_task(job_id)

            event2 = ws.receive_json()
            assert event2["status"] == "running"

            event3 = ws.receive_json()
            assert event3["status"] == "completed"
            assert event3["result"] == {"message": "Realtime Hello"}
