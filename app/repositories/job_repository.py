from uuid import UUID
from sqlalchemy.orm import Session
from database.models import Job, JobStatus

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
