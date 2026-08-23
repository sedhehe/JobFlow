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
