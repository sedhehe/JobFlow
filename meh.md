22/08/2026
first when payload is recieved via /jobs, the incoming payload is validated via pydantic in models/jobs.py checking JobsPayload
JobsPayload checks what type of payload it is via discriminator
the payload builds up in a nested validation from the outside in. 
eg:
    {
        type: "echo",
        message: "hello"
    }
    this is what is passed to the create jobs api call

    the create jobs api call wants JobsPayload structure so it checks with JobsPayload in models/jobs.py
    JobsPayload checks type.
    here type is echo 'type: "echo"' so EchoJob model is assigned
    now EchoJob model will check type and says "yes this is echo, this is mine, let me check payload structure now" and it checks payload structure which is EchoPayload
    then EchoPayload checks the payload and validates it. checks if all the required fields are present and have the correct data types.
    eg: 'message: "hello"' -> this is string, and EchoPayload expects string, so it validates it
    
now a job is successfully created and is stored in jobs_db which is in storage/jobs.py

get all jobs by literally returning jobs_db and each job by literally returning jobs by their id like this jobs_db[job_id]

now to run a job that is created we use /run endpoint which calls run_job function in services/job_service.py
job_service.py takes id to know what job to run
after the job is fetched, the job's type is fetched and check whether we have it or not in handlers which is in handlers/registry.py which is a mapping of type and their function.
now if the type is valid and we have a handler for it then the handler.execute(job.payload) is called and the result is returned while also updating the status and storing in the jobs_db.
eg:
    run the above created job
    check jobs_db for the job and fetch it
    check it's type
    check registry handlers for the handler
    now type is echo, we have the handler for it
    so handler.execute(job.payload) i.e. EchoHandler.execute(job.payload) runs and returns the results and then the jobs_db is updated with the result and status is updated to completed and returned

now here handler is a mapping of type and their function and the function is in handlers/echo.py and handlers/addition.py which validates their payloads using models/jobs.py

models    → "What does the data look like?"
handlers  → "How do I actually perform this job?"
services  → "What is the business logic/workflow?"
storage   → "Where do I keep the data?"
main.py   → "How does the outside world talk to my application?"

jobflow/
└──app/
    ├── main.py
    │
    ├── models/
    │   └── jobs.py
    │
    ├── handlers/
    │   ├── echo.py
    │   ├── addition.py
    │   └── registry.py
    │
    ├── services/
    │   └── job_service.py
    │
    └── storage/
        └── jobs.py
    

23/08/2026
introduced /database, responsible for database, tables stuff.
database/connection.py creates connection with my postgres db hosted on my hardware.
database/models.py defines the schema of the tables i want to create.
database/alembic creates migrations for the tables.

models/jobs.py                                 database/models.py
       │                                               │
       └── "Is this API data valid?"                   └── "How should this data be stored?"

why alembic?
Alembic is a migration tool for SQLAlchemy. It is used to manage database migrations, which are changes to the database schema that are tracked over time.
with the help of alembic, for every table change we don't have to manually alter the table schem or drop tables and lose all data. instead we just update the models and alembic will create a migration file for us which we can run to update the table schema.
setup - first alembic init alembic
then in alembic/env.py update "target_metadata" with our metadata which is defined in database/models.py
paste db link in alembic.ini file
check with alembic check
now for every table change, just update the models and run alembic revision --autogenerate -m "<upgrade_message>" and then alembic upgrade head

our table:
              jobs
        ┌──────────────────────────┐
        │ id          UUID         │
        │ type        VARCHAR      │
        │ status      ENUM         │
        │ payload     JSONB        │
        │ result      JSONB        │
        │ created_at  TIMESTAMP    │
        │ updated_at  TIMESTAMP    │
        └──────────────────────────┘

The process now:
                 HTTP REQUEST
                      │
                      ▼
             ┌─────────────────┐
             │ Pydantic Models  │
             │ models/jobs.py   │
             └────────┬────────┘
                      │
                      │ validated Python data
                      ▼
             ┌─────────────────┐
             │    Service      │
             │ job_service.py  │
             └────────┬────────┘
                      │
                      ▼
             ┌─────────────────┐
             │   Repository    │
             │ job_repository  │
             └────────┬────────┘
                      │
                      ▼
             ┌─────────────────┐
             │ SQLAlchemy Model │
             │ database/models  │
             └────────┬────────┘
                      │
                      ▼
             ┌─────────────────┐
             │   PostgreSQL    │
             │   jobs table    │
             └─────────────────┘

24/08/2026
creating job_repository, was writing the "get_job_by_id" function to get the job from table by id, there a question i got, self.db.get(Job, job_id) is taking Job which is imported from databaase/models. How is that linked to or helpful to search the right table?
ans: Job is a Python class, but it is linked to the PostgreSQL table jobs (__tablename__ = "jobs").
     When you pass Job to SQLAlchemy, it automatically generates SQL for the jobs table:
     self.db.get(Job, job_id) translates to SELECT * FROM jobs WHERE id = <job_id>;
     self.db.query(Job).all() translates to SELECT * FROM jobs;
    
damn okay, SQLAlchemy is really alchemy, when the fetched job is modified self.db.commit() automatically writes the UPDATE SQL to PostgreSQL!

Now connecting FastAPI and repository.

When User A and User B send requests at the exact same time, FastAPI runs get_db() independently for each of them.
User A gets Session 1
User B gets Session 2
They are completely isolated in PostgreSQL and do not interfere with each other.
this is to prevent: Broken Transactions (Atomicity).
eg: if user A and user B are in same session and user A's job fails in between then both jobs are rolled back and user b's job is not completed. user A's job fails and user B's job is not completed successfully.
that's why we create a session using FastAPI get_db() to create independent sessions for each request.

current flow:
Incoming HTTP Request (JSON)
        ↓
Pydantic Model (JobsPayload)  ← validates request data
        ↓
SQLAlchemy Model (Job)        ← translated into database row
        ↓
JobRepository (create / get)  ← saves/reads from PostgreSQL
        ↓
Pydantic Model (JobsResponse) ← formats output sent back to client

in main.py i.e. our FastAPI, we now wait for the endpoint to get db connection using Depends(get_db) (get_db from database/connection.py) and store the result in db of type Session becuase we are craeting a session, until we get something nothing is done.
after we get db from get_db we instantiate job_repository using JobRepository(db) saying, here is the db object (session) and now do your operations.

okay, so the flow is like this:
first endpoint method is called
sees it needs the db which is of type JobRepo
goes to JobRepo which is of type JobRepository and sees it needs to call get_job_repo
calls get_job_repo which needs db of type sessiong and calls get_db
once we get db we pass it to JobRepo, and JobRepo goes to create_job, see repo.create and writes into db and closes

now in services/job_service.py takes in the repo and gets the job by id using repo.get_job_by_id(job_id).
The payload coming from the database is a raw Python dictionary (`job.payload = {"message": "hello"}`), but our handlers expect a Pydantic model so they can access attributes via dot notation (`payload.message`).
To keep handlers flexible (Open-Closed Principle), each handler now defines its own `payload_schema` class attribute (e.g. `EchoHandler.payload_schema = EchoPayload`).
In `job_service.py`, we convert the dictionary using dictionary unpacking `**`:
`payload = handler.payload_schema(**job.payload)`
The `**` operator "unzips" the dictionary `{"message": "hello"}` into named keyword arguments `message="hello"`, so Pydantic parses it into `EchoPayload(message="hello")`.

Why modify `job.status = JobStatus.COMPLETED` directly instead of creating a new `updated_job` object?
In SQLAlchemy ORM, the `job` object returned by `repo.get_job_by_id(job_id)` is already attached to and tracked by the active database session in memory.
When we modify its attributes directly (`job.status = JobStatus.COMPLETED` and `job.result = result`) and call `repo.update(job)` (`self.db.commit()`), SQLAlchemy automatically detects the changes and generates the `UPDATE jobs SET status=..., result=... WHERE id=...` SQL query for us! There is no need to reconstruct a new object.