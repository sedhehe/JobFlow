from uuid import UUID
from redis import Redis
import json
from database.models import Job
from models.jobs import JobsResponse

redis_client = Redis(host='localhost', port=6379, decode_responses=True)

class JobCache():
    def __init__(self, client: Redis | None = None):
        self.client = client or redis_client

    def get(self, job_id: UUID) -> dict | None:
        key = f"job:{job_id}"
        data = self.client.get(key)

        if data is None:
            return None
        return json.loads(data)
        
    def set(self, job: Job, ttl: int = 60) -> None:
        key = f"job:{job.id}"
        data = JobsResponse.model_validate(job, from_attributes=True).model_dump_json() # doing <--- this instead of "json.dumps(job)" because that causes "TypeError: Object of type Job is not JSON serializable" because job is of type Job which is and SQLAlchemy model and json.dumps only works with primitive python types
        self.client.set(key, data, ex=ttl)

    def delete(self, job_id: UUID) -> None:
        key = f"job:{job_id}"
        self.client.delete(key)
        

    


    