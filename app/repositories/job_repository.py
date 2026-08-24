from uuid import UUID
from sqlalchemy.orm import Session
from database.models import Job

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

    def get_all_jobs(self):
        return self.db.query(Job).order_by(Job.created_at.desc()).all()

    def update(self, job:Job):
        self.db.commit()
        self.db.refresh(job)
        return job
