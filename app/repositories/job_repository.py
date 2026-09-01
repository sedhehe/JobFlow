from uuid import UUID
from sqlalchemy.orm import Session
from database.models import Job, JobStatus
from datetime import datetime as dt, timezone, timedelta

class JobRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, job: Job):
        self.db.add(job)        # stages new job in the session like git add
        self.db.commit()        # writes and saves the action/job to the db like git commit then git push
        self.db.refresh(job)    # reloads the objoect after db update
        return job

    def get_job_by_id(self, job_id: UUID):
        job = self.db.get(Job, job_id) 
        if not job:
            return None
        return job

    def get_all_jobs(self,
    limit: int = 10,
    status: JobStatus | None = None,
    type: str | None = None,
    offset: int = 0) -> list[Job]:
        query = self.db.query(Job)

        # filter by status
        if status is not None:
            query = query.filter(Job.status == status)

        # filter by type
        if type is not None:
            query = query.filter(Job.type == type)

        return query.order_by(Job.created_at.desc()).offset(offset).limit(limit).all()

    def update(self, job:Job):
        self.db.commit()
        self.db.refresh(job)
        return job

    def ping_heartbeat(self, job_id: UUID) -> None:
        job = self.get_job_by_id(job_id)
        if job and job.status == JobStatus.RUNNING:
            job.updated_at = dt.now(timezone.utc)
            self.db.commit()
    
    def recover_zombies(self, max_idle_minutes: int = 15) -> int:
        cutoff = dt.now(timezone.utc) - timedelta(minutes=max_idle_minutes)

        zombies = self.db.query(Job).filter(
            Job.status == JobStatus.RUNNING, Job.updated_at < cutoff
        ).all()

        for job in zombies:
            job.status = JobStatus.FAILED
            job.error_message = f"Worker heartbeat lost for > {max_idle_minutes} minutes (Worker crashed)"
            self.update(job)

        return len(zombies)

    def prune_old_jobs(self, retention_days: int = 30) -> int:
        cutoff = dt.now(timezone.utc) - timedelta(days=retention_days)
        
        deleted_count = self.db.query(Job).filter(
            Job.status.in_([JobStatus.COMPLETED, JobStatus.FAILED]),
            Job.created_at < cutoff
        ).delete(synchronize_session=False)
        self.db.commit()
        return deleted_count
