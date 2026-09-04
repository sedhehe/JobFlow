from uuid import UUID
from celery_app import celery_app
from database.connection import SessionLocal
from repositories.job_repository import JobRepository
from database.models import JobStatus
from cache.redis import JobCache
from queues.queue import JobQueue
from services.job_service import run_job
from realtime.pubsub import publish_job_event

@celery_app.task(bind=True, max_retries=5)
def execute_job_task(self, job_id_str: str):
    job_id = UUID(job_id_str)
    db = SessionLocal()
    cache = JobCache()
    job_queue = JobQueue()

    try:
        repo = JobRepository(db)
        publish_job_event(job_id, {"status": "running", "job_id": str(job_id)})
        job = run_job(job_id, repo)
        cache.delete(job.id)
        
        
        if job.status == JobStatus.FAILED:
            if self.request.retries >= self.max_retries:
                job_queue.enqueue_dlq(job_id)
                publish_job_event(job_id, {"status": "failed retrying...", "job_id": str(job.id)})
                return {"status": "failed", "job_id": str(job.id), "dlq": True}
            
            raise self.retry(countdown=2 ** self.request.retries)

        publish_job_event(job_id, {"status": "completed", "job_id": str(job.id), "result": job.result})
        return {"status": job.status.value, "job_id": str(job.id)}

    except Exception as e:
        cache.delete(job_id)

        if self.request.retries >= self.max_retries:
            job_queue.enqueue_dlq(job_id)
            publish_job_event(job_id, {"status": "failed ", "job_id": str(job_id)})
            raise e
        # Celery's built-in exponential backoff retry!
        raise self.retry(exc=e, countdown=2 ** self.request.retries)
    finally:
        db.close()

@celery_app.task
def cleanup_stale_jobs_task():
    db = SessionLocal()
    try:
        repo = JobRepository(db)
        zombies = repo.recover_zombies(max_idle_minutes=15)
        pruned = repo.prune_old_jobs(retention_days=30)
        print(f"🧹 Celery Beat Cleanup: {zombies} zombies recovered, {pruned} old jobs pruned.")
    finally:
        db.close()

