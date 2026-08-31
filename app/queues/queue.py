from uuid import UUID
from cache.redis import redis_client
from redis.client import Redis

class JobQueue:
    def __init__(self, client: Redis | None = None):
        self.client = client or redis_client
        self.queue_name = "job:queue"
        self.dlq_name = "job:dlq"

    def enqueue(self, job_id: UUID) -> None :
        self.client.lpush(self.queue_name, str(job_id))

    def dequeue(self, timeout: int = 5) -> UUID | None :
        data = self.client.brpop(self.queue_name, timeout=timeout)

        if data is None:
            return None
        else:
            job_id = str(data[1])
            return UUID(job_id)

    def enqueue_dlq(self, job_id: UUID) -> None :
        self.client.lpush(self.dlq_name, str(job_id))

    def get_dlq_jobs(self, ) -> list[UUID]:
        dead_jobs = self.client.lrange(self.dlq_name, 0, -1)

        return [UUID(str(job_id)) for job_id in dead_jobs]

