# JobFlow — Developer Notes & Learning Log

---

## 22/08/2026 — Core Architecture & In-Memory Flow

### 1. Request Validation via Pydantic (`models/jobs.py`)
- When a payload is received via `POST /jobs`, the incoming JSON is validated via Pydantic in `models/jobs.py` checking `JobsPayload`.
- `JobsPayload` checks what type of payload it is via a **discriminator field** (`type`).
- The payload builds up in a **nested validation from the outside in**.

#### Example:
```json
{
    "type": "echo",
    "payload": {
        "message": "hello"
    }
}
```
1. This JSON is passed to the create jobs API call.
2. The create jobs API call expects the `JobsPayload` structure, so it checks with `JobsPayload` in `models/jobs.py`.
3. `JobsPayload` checks the `type`.
4. Here `type` is `"echo"`, so the `EchoJob` model is assigned.
5. The `EchoJob` model checks the type and says: *"Yes this is echo, this is mine, let me check payload structure now"*, and checks the payload structure which is `EchoPayload`.
6. Then `EchoPayload` checks the payload and validates it. It verifies that all required fields are present and have the correct data types.
   - Example: `"message": "hello"` is a string, and `EchoPayload` expects a string, so it validates successfully.

---

### 2. In-Memory Job Storage (`storage/jobs.py`)
- Once a job is successfully created, it is stored in `jobs_db` in `storage/jobs.py`.
- **Get all jobs:** Returns `jobs_db.values()`.
- **Get job by ID:** Looks up the job directly by ID: `jobs_db[job_id]`.

---

### 3. Job Execution Workflow (`services/job_service.py`)
- To run a created job, we use the `POST /jobs/{job_id}/run` endpoint, which calls `run_job(job_id)` in `services/job_service.py`.
- `job_service.py` takes the `job_id` to know what job to run.
- After the job is fetched, the job's `type` is checked against `handlers` in `handlers/registry.py` (a registry mapping job types to handler instances).
- If the type is valid and a handler exists:
  - `handler.execute(job.payload)` is called.
  - The result is returned.
  - The job's status is updated to `completed`.
  - The updated job is stored in `jobs_db`.

#### Example Trace:
1. Run the above created job.
2. Check `jobs_db` for the job and fetch it.
3. Check its type.
4. Check `registry` for the matching handler.
5. If type is `"echo"`, we have the handler for it.
6. `handler.execute(job.payload)` (i.e. `EchoHandler.execute(job.payload)`) runs and returns the result.
7. `jobs_db` is updated with the result and status is updated to `completed`.

---

### 4. Responsibilities by Layer

| Layer | File | Core Responsibility |
| :--- | :--- | :--- |
| **Models** | `models/jobs.py` | *"What does the data look like?"* |
| **Handlers** | `handlers/*.py` | *"How do I actually perform this job?"* |
| **Services** | `services/job_service.py` | *"What is the business logic / workflow?"* |
| **Storage** | `storage/jobs.py` | *"Where do I keep the data?"* |
| **API** | `main.py` | *"How does the outside world talk to my application?"* |

#### Project Structure:
```text
jobflow/
└── app/
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
```

---

## 23/08/2026 — Database, SQLAlchemy & Alembic Setup

### 1. Database Introduction (`/database`)
Introduced `/database` directory, responsible for database connection, models, and migrations:
- `database/connection.py`: Creates connection with PostgreSQL database hosted on local machine.
- `database/models.py`: Defines the SQLAlchemy ORM schema of the tables.
- `database/alembic`: Manages database schema migrations over time.

```text
models/jobs.py                                 database/models.py
       │                                               │
       └── "Is this API data valid?"                   └── "How should this data be stored?"
```

---

### 2. Why Alembic?
- Alembic is a database migration tool for SQLAlchemy used to track and manage changes to database schemas over time.
- With Alembic, for every table change we don't have to manually run `ALTER TABLE` or drop tables and lose all data. Instead, we update SQLAlchemy models and Alembic generates migration files to apply schema changes safely.

#### Setup & Migration Workflow:
1. Initialize Alembic: `alembic init alembic`
2. In `alembic/env.py`, set `target_metadata = Base.metadata` (from `database.models`).
3. Set database URL in `alembic.ini`.
4. Check differences: `alembic check`
5. Generate migration: `alembic revision --autogenerate -m "<upgrade_message>"`
6. Apply migration: `alembic upgrade head`

#### Database Table Schema (`jobs`):
```text
              jobs
        ┌──────────────────────────┐
        │ id          UUID         │
        │ type        VARCHAR(50)  │
        │ status      ENUM         │
        │ payload     JSONB        │
        │ result      JSONB        │
        │ created_at  TIMESTAMP    │
        │ updated_at  TIMESTAMP    │
        └──────────────────────────┘
```

#### Layered Architecture Flow:
```text
                 HTTP REQUEST
                      │
                      ▼
             ┌─────────────────┐
             │ Pydantic Models  │
             │ models/jobs.py   │
             └────────┬────────┘
                      │
                      │ (validated Python data)
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
```

---

## 24/08/2026 — Repository Layer, Dependency Injection, SQLAlchemy & Scaling

### 1. JobRepository & SQLAlchemy Querying
When creating `job_repository.py` and writing `get_job_by_id`:
- **Question:** `self.db.get(Job, job_id)` takes `Job` imported from `database/models`. How is that linked or helpful to search the right table?
- **Answer:** `Job` is a Python class linked to the PostgreSQL `jobs` table (`__tablename__ = "jobs"`). When you pass `Job` to SQLAlchemy, it automatically generates SQL for the `jobs` table:
  - `self.db.get(Job, job_id)` translates to: `SELECT * FROM jobs WHERE id = <job_id>;`
  - `self.db.query(Job).all()` translates to: `SELECT * FROM jobs;`

> **Key takeaway:** SQLAlchemy is really alchemy! When a fetched job object is modified, calling `self.db.commit()` automatically writes the `UPDATE` SQL to PostgreSQL.

---

### 2. Connecting FastAPI and Repository (Session-per-Request)
- When User A and User B send requests at the exact same time, FastAPI runs `get_db()` independently for each of them.
  - User A gets **Session 1**
  - User B gets **Session 2**
- They are completely isolated in PostgreSQL and do not interfere with each other.
- **Why?** To prevent **Broken Transactions (Atomicity)**.
  - *Example:* If User A and User B were in the same session and User A's transaction failed midway, both operations would be rolled back and User B's valid job would be lost.
  - Creating independent sessions per request via `get_db()` isolates transactions safely.

#### End-to-End Data Transformation Flow:
```text
Incoming HTTP Request (JSON)
        ↓
Pydantic Model (JobsPayload)  ← validates request data
        ↓
SQLAlchemy Model (Job)        ← translated into database row
        ↓
JobRepository (create / get)  ← saves/reads from PostgreSQL
        ↓
Pydantic Model (JobsResponse) ← formats output sent back to client
```

#### Dependency Injection Chain in `main.py`:
1. In `main.py`, endpoints request a DB connection using `Depends(get_db)` (from `database/connection.py`).
2. `get_db()` yields a session of type `Session`.
3. `get_job_repo(db)` instantiates `JobRepository(db)` and provides it to endpoints via `JobRepo = Annotated[JobRepository, Depends(get_job_repo)]`.

#### Request Execution Trace:
1. Endpoint method is called.
2. Sees it needs `repo` of type `JobRepo`.
3. FastAPI inspects `JobRepo` and sees it depends on `get_job_repo`.
4. `get_job_repo` needs `db: Session`, so FastAPI calls `get_db`.
5. `get_db` opens a session and yields `db`.
6. `get_job_repo(db)` creates and returns `JobRepository(db)`.
7. FastAPI passes `repo` into the endpoint function.
8. The endpoint runs `repo.create(job)` / queries the database.
9. Response is returned, and FastAPI cleanly closes the session in `get_db()`.

---

### 3. Service Layer Payload Conversion & In-Place ORM Mutation

#### Payload Conversion via Dictionary Unpacking (`**`):
- `services/job_service.py` receives `repo` and fetches the job by ID using `repo.get_job_by_id(job_id)`.
- The payload coming from PostgreSQL is a raw Python dictionary (`job.payload = {"message": "hello"}`), but handlers expect a Pydantic model so they can access attributes via dot notation (`payload.message`).
- To keep handlers flexible (Open-Closed Principle), each handler defines its own `payload_schema` class attribute (e.g. `EchoHandler.payload_schema = EchoPayload`).
- In `job_service.py`, we convert the dictionary using dictionary unpacking `**`:
  ```python
  payload = handler.payload_schema(**job.payload)
  ```
- The `**` operator unzips the dictionary `{"message": "hello"}` into named keyword arguments `message="hello"`, allowing Pydantic to parse it into `EchoPayload(message="hello")`.

#### Why Mutate `job.status = JobStatus.COMPLETED` Directly?
- In SQLAlchemy ORM, the `job` object returned by `repo.get_job_by_id(job_id)` is already attached to and tracked by the active database session in memory.
- When we modify its attributes directly:
  ```python
  job.status = JobStatus.COMPLETED
  job.result = result
  ```
  and call `repo.update(job)` (`self.db.commit()`), SQLAlchemy automatically detects the changes and generates the `UPDATE jobs SET status=..., result=... WHERE id=...` SQL query. There is no need to construct a new object.

---

### 4. Architectural Scaling Upgrades

#### A. Decorator-Based Auto-Discovery (`handlers/registry.py`)
- **Problem:** Manually importing and adding every handler into `handlers/registry.py` causes that file to balloon as the number of job types grows.
- **Solution:** Introduced the `@register_handler("type_name")` decorator and `discover_handlers()`.
- **How it works:** When the application boots, `discover_handlers()` uses `pkgutil.iter_modules()` to automatically discover and import every module in the `handlers/` package. Each handler registers itself upon import. Adding a new job type requires **zero edits** to `registry.py`.

#### B. Decentralized Handler-Driven Validation (`models/jobs.py`)
- **Problem:** Having a giant union in `models/jobs.py` (`JobsPayload = Annotated[EchoJob | AddJob | DivisionJob | ...]`) forces every new job type to edit a central schema file.
- **Solution:**
  - `JobsPayload` and `JobsResponse` use generic `payload: dict`.
  - In `handlers/<job_type>.py`, each handler defines its own local `payload_schema = ...` (e.g. `DivisionPayload`).
  - In `POST /jobs`, FastAPI accepts the request and validates the `dict` using `handler.payload_schema.model_validate(body.payload)`. If invalid, it returns `422 Unprocessable Entity` with exact validation errors.

#### C. Job Lifecycle & Safe Execution (`services/job_service.py`)
- **State Machine:** `CREATED` ➔ `RUNNING` ➔ `COMPLETED` or `FAILED`.
- **Error Handling:** Handlers are wrapped in a `try...except Exception as e:` block. If execution throws an error (e.g. division by zero), the job transitions to `FAILED` and records `{"error": str(e)}` in PostgreSQL instead of crashing the server with a 500 error.