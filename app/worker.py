from database.connection import SessionLocal
from repositories.job_repository import JobRepository
from cache.redis import JobCache
from queues.queue import JobQueue
from services.job_service import run_job
from database.models import JobStatus
import time

def run_worker():
    job_queue = JobQueue()
    cache = JobCache()

    print("🚀 Worker is running and waiting for jobs...")

    
    while True:
        job_id = job_queue.dequeue(timeout=5)

        if job_id is None:
            continue

        db = SessionLocal()

        try:
            repo = JobRepository(db)
            job = run_job(job_id, repo)
            cache.delete(job_id)

            if job.status == JobStatus.FAILED:
                if job.retry_count < job.max_retries:
                    job.retry_count += 1
                    delay = 2 ** job.retry_count
                    time.sleep(delay)
                    job.status = JobStatus.QUEUED
                    repo.update(job)
                    job_queue.enqueue(job_id)
                else:
                    job.status = JobStatus.FAILED
                    repo.update(job)
                    job_queue.enqueue_dlq(job_id)
                    cache.delete(job_id)

        except Exception as e:
            print(f"Error: {e}")
            
        finally:
            db.close()

if __name__ == "__main__":
    run_worker()
            
