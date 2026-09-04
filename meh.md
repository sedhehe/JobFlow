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
models/jobs.py                          database/models.py
       │                                        │
       └── "Is this API data valid?"            └── "How should this data be stored?"
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

---

## 25/08/2026 — Unit & Integration Tests using Pytest

- Wrote unit tests in the `/tests` folder following the same structure as `app/`, with the only difference being that test files are named `test_{name}.py` because pytest automatically discovers files with the `test_` prefix.
- In unit tests, we test every case for the handlers:
  - We verify expected results using `assert`.
  - For expected errors, we test using:
    ```python
    with pytest.raises({error}):
        handler.execute(payload)
    ```
- Wrote integration tests for the API covering all cases and testing the entire job lifecycle.
- To run tests: execute `pytest` in the root folder.
- `pyproject.toml` acts like `package.json` in React, storing all tool configurations.
- `.vscode/settings.json` configures the IDE.
- These configuration files set `/app` as the root directory for tests and IDE analysis to eliminate import error squiggly lines.

---

## 26/08/2026 — Pagination & Query Filtering

Implemented dynamic filtering and pagination in `JobRepository`:

```python
def get_all_jobs(
    self,
    limit: int = 10,
    status: JobStatus | None = None,
    type: str | None = None,
    offset: int = 0
) -> list[Job]:
    query = self.db.query(Job)

    # Filter by status
    if status is not None:
        query = query.filter(Job.status == status)

    # Filter by type
    if type is not None:
        query = query.filter(Job.type == type)

    return (
        query.order_by(Job.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
```

- Straightforward and clean query building.

---

## 27/08/2026 — ACID Transactions, Docker & Redis Caching

### 1. ACID Transactions & Rollback
- When a database action is happening for one user and it fails, that user and subsequent users will face issues with broken/aborted transactions.
- **Solution:** In `database/connection.py`, we add an `except Exception:` block to catch errors and roll back the transaction using `db.rollback()`, and then `finally` close the connection and session.
- `db.rollback()` safely discards any half-written or corrupted transactions.

---

### 2. Docker & Docker Compose
- **The Problem:** Manually starting our PostgreSQL server and now Redis server is tedious. In the future, as we add more services, manually starting and remembering every service causes massive headaches and debugging issues if one is missed.
- **The Solution:** With Docker, we can launch every single required service with one command (`docker compose up -d`) and shut them down cleanly with `docker compose down`.
- Configured in a single file: `docker-compose.yml`.
- We put every service in a container. What the container contains is defined by the `image`, and runtime parameters (like port mappings and volumes) are configured declaratively:

```yaml
services:
  postgres: # Container for Postgres
    image: postgres:latest # Postgres image
    ports:
      - "5432:5432" # Map host port 5432 to container port 5432
    environment:
      POSTGRES_DB: jobflow # Set db name
      POSTGRES_USER: vivekrallapally # Set db user
      POSTGRES_HOST_AUTH_METHOD: trust # No password required
    volumes:
      - postgres_data:/var/lib/postgresql/data # Persistent storage volume

  redis: # Container for Redis
    image: redis:latest # Redis image
    ports:
      - "6379:6379" # Map host port 6379 to container port 6379

volumes:
  postgres_data:
```

---

### 3. Redis Caching
- **Redis:** A super-fast in-memory data storage and retrieval system used for caching.
- **Why Caching?** If the same data is retrieved repeatedly by multiple users, fetching from the database every time is slow and expensive.
- **Cache-Aside Pattern:**
  1. Fetch data once from PostgreSQL and store it in cache (Redis).
  2. When a user requests that data, first check the cache.
  3. **If found (HIT):** Return faster results with zero database load.
  4. **If not found (MISS):** Fetch from DB and store in cache for later use.

#### Implementation Details (`app/cache/redis.py`):
- Initialized Redis connection client using `Redis(host, port, decode_responses=True)`.
- Created `JobCache` class with core caching operations: `get`, `set`, and `delete`.
- **Key Namespacing:** In Redis, data is stored as a global key-value store `{"key1": "data1", "key2": "data2"}`. To prevent two different entities (like `job:123` and `user:123`) from overwriting each other, we prefix keys with their namespace: `f"job:{job_id}"`.
- **`get(job_id)`:** Retrieves data from Redis using the namespaced key.
- **`set(job, ttl)`:** Takes the job as `database.models.Job` (SQLAlchemy model), converts it to `models.jobs.JobsResponse` using `model_validate(job, from_attributes=True).model_dump_json()`, and sets it in cache with an expiration time (`ttl`).
  - *Why conversion is necessary:* Redis stores data as strings. Passing a raw SQLAlchemy `Job` directly into `json.dumps()` throws `TypeError: Object of type Job is not JSON serializable` because `json.dumps()` only handles Python primitives. Pydantic handles serializing UUIDs, Datetimes, and ORM objects cleanly to JSON.
- **`delete(job_id)`:** Deletes the key on state mutation.

#### Complete Request Flow:
1. **Job Created:** Saved to PostgreSQL.
2. **First `GET /jobs/{id}` (Cache Miss):** Checked in Redis (not found) ➔ fetched from PostgreSQL ➔ saved to Redis cache with TTL.
3. **Subsequent `GET /jobs/{id}` (Cache Hit):** Checked in Redis (found) ➔ returned directly from cache in sub-milliseconds.
4. **Job Executed / State Updated:** Invalidate/delete the key from Redis cache (`cache.delete(job_id)`) so stale/old data is never returned to users.

## 30/08/2026 — Job Queues, Background Workers & Horizontal Scaling

- **Job Queue:** Created a FIFO queue in `queues/queue.py` backed by Redis with key namespacing (`"job:queue"`).
  - **Enqueue (`lpush`):** Pushes job IDs onto the left of the Redis list.
  - **Dequeue (`brpop`):** Blocking pop from the right of the Redis list with a timeout, putting the worker to sleep with 0% CPU when idle.
- **Worker Process (`worker.py`):**
  - Runs in an infinite loop calling `queue.dequeue()`.
  - If no job is found within 5s, it continues waiting.
  - When a job arrives, opens a fresh database session, executes `run_job(job_id, repo)`, invalidates cache, and closes the session in a `finally` block.

#### Updated End-to-End Flow:
1. **Job Creation (`POST /jobs`):** Payload validated via Pydantic (`models/jobs.py`) ➔ saved to PostgreSQL with status `CREATED` (validated via SQLAlchemy model `database/models.py`). Cache and Queue remain untouched (lazy loading).
2. **First Read (`GET /jobs/{id}`):** Cache checked (miss) ➔ fetched from PostgreSQL ➔ saved to Redis cache with 60s TTL.
3. **Job Enqueued (`POST /jobs/{id}/run`):** Fetches job from PostgreSQL ➔ updates status to `QUEUED` ➔ deletes stale `"created"` cache from Redis ➔ pushes `job_id` to Redis queue ➔ immediately returns `202 Accepted` in ~2ms.
4. **Worker Picks Up Job:** Worker pops `job_id` from Redis queue ➔ marks status `RUNNING` in DB ➔ deletes stale `"queued"` cache ➔ calls `run_job(job_id, repo)`.
   - Inside `run_job`: Loads handler using `job.type` and executes calculation.
   - If execution fails ➔ status updated to `FAILED`.
   - If execution succeeds ➔ status updated to `COMPLETED` with `result` stored in DB.
5. **Session Cleanup:** Worker closes the DB session.
6. **Subsequent Read (`GET /jobs/{id}`):** Fetches updated `COMPLETED` status from DB on first miss, caches it in Redis, and serves all subsequent reads directly from Redis in 0.1ms!

- **Horizontal Scaling:** We can launch multiple worker processes in separate terminal tabs/containers. Redis automatically load balances jobs across all active workers with zero race conditions!

---

## 31/08/2026 — Failure Recovery, Retries & Dead Letter Queue (DLQ)

- **Dead Letter Queue (DLQ):** Created a secondary queue in Redis under the key namespace `"job:dlq"`.
  - **`enqueue_dlq(job_id)`:** Pushes persistently failing job IDs to the DLQ.
  - **`get_dlq_jobs()`:** Reads all quarantined jobs from the DLQ for inspection and debugging.
  - *Why no dequeue?* We don't want to pop/delete items automatically; we want them quarantined so engineers can view logs, investigate bugs, and inspect corrupted payloads!

- **Retry Mechanism & Exponential Backoff:**
  - When a job fails, we increment `retry_count` (up to `max_retries = 5`).
  - To prevent spamming external servers, we delay retries exponentially ($2^{\text{retry\_count}}$ seconds: $2\text{s} ➔ 4\text{s} ➔ 8\text{s} ➔ 16\text{s} ➔ 32\text{s}$).
  - Once retries are exhausted (`retry_count >= max_retries`), the job status is set to `FAILED`, the error message is persisted in PostgreSQL, the job is moved to the DLQ, and the cache key is deleted.

## 01/09/2026 — Celery Architecture & Dynamic Multi-Queue Routing

- **Celery Application (`app/celery_app.py`):**
  - Configured Celery as the central task orchestration hub.
  - **Name:** `"jobflow"` (hub identifier).
  - **Broker:** Redis DB 0 (`redis://localhost:6379/0`) where tasks wait in queues.
  - **Backend:** Redis DB 1 (`redis://localhost:6379/1`) where workers store task completion results and state.
  - **Multi-Queue Routing (Priority Lanes):**
    - `high_priority`: Fast, lightweight jobs (e.g. `echo`, `add`).
    - `default`: Standard jobs (e.g. `division`).
    - `low_priority`: Heavy background jobs (e.g. video processing, bulk exports).
  - **Autodiscover:** Configured `autodiscover_tasks(["tasks"])` to register task modules dynamically.

- **Distributed Task Definition (`app/tasks/job_tasks.py`):**
  - Created `execute_job_task` decorated with `@celery_app.task(bind=True, max_retries=5)`.
  - Opens an isolated database session per execution, runs `run_job()`, and invalidates cache.
  - **Automated Exponential Backoff & DLQ Quarantine:**
    - Uses Celery's built-in `self.retry(countdown=2 ** self.request.retries)`.
    - When all 5 retries are exhausted (`self.request.retries >= self.max_retries`), the task automatically quarantines the job ID to our Dead Letter Queue (`job_queue.enqueue_dlq(job_id)`) and raises the exception.

- **Open-Closed Principle & Decorator Factories:**
  - Enhanced `@register_handler(job_type, priority="default")` into a decorator factory.
  - Handlers declare their own priority metadata (e.g. `EchoHandler` declares `priority="high_priority"`).
  - `POST /jobs/{id}/run` in `main.py` reads `handler.priority` and dispatches via `execute_job_task.apply_async(args=[str(job_id)], queue=priority_queue)` with zero hardcoded `if-elif-else` statements.
  - Celery serializes the task into a standard JSON envelope and performs the `LPUSH` into Redis automatically!

- **Scheduled Maintenance with Celery Beat (`app/tasks/job_tasks.py` & `app/repositories/job_repository.py`):**
  - Configured `beat_schedule` to run `cleanup_stale_jobs_task` periodically (every hour).
  - **The Worker Heartbeat Pattern (`ping_heartbeat`):** Workers executing long tasks periodically update `job.updated_at = NOW`.
  - **Zombie Job Recovery (`recover_zombies`):** If a worker abruptly crashes or gets OOM-killed while running a job, its heartbeats stop. If `updated_at < (NOW - 15 minutes)`, Celery Beat identifies the dead job and marks it as `FAILED` with an explanatory error message.
  - **Data Retention Pruning (`prune_old_jobs`):** Automatically hard deletes finished (`COMPLETED` / `FAILED`) rows older than 30 days (`created_at < NOW - 30 days`) to prevent database bloat and keep query performance lightning fast.

- **Migration to Production Celery Architecture:**
  - Transitioned from manual in-house worker loop (`app/worker.py` and `app/queues/`) to production-grade Celery orchestration (`app/celery_app.py` and `app/tasks/job_tasks.py`).

## 02/09/2026 — Level 8: Real-Time State Streaming (WebSockets + Redis Pub/Sub)

- **Architecture & Responsibilities (`app/realtime/`):**
  - **`ConnectionManager` (`app/realtime/connection_manager.py`):**
    - Stores active connections using: `{job_id: list[WebSocket]}`.
    - Responsible for accepting connections, disconnecting on client exit, and pushing messages to clients via `broadcast_to_job()`.
  - **`pubsub` (`app/realtime/pubsub.py`):**
    - Responsible for publishing events and listening for updates across servers.
    - **Publishing:** Uses `redis_client.publish(f"job_events:{job_id}", json.dumps(event))` where `job_events:{job_id}` is the channel topic and `event` contains job state data.
    - **Subscribing:** Uses `pubsub = r.pubsub()` and `await pubsub.psubscribe("job_events:*")` to listen to all job channels asynchronously.
    - Extracts `job_id` and `event_data` from incoming messages and forwards them to `connection_manager.broadcast_to_job()`.

- **FastAPI Integration (`app/main.py`):**
  - Added `@app.websocket("/ws/jobs/{job_id}")` endpoint to manage persistent socket sessions and gracefully handle `WebSocketDisconnect`.
  - Added a background startup task using FastAPI's `lifespan` context manager to run `start_redis_listener(manager)` continuously.

- **Lifecycle Event Publishing (`publish_job_event`):**
  - **Created / Enqueued:**
    `publish_job_event(job.id, {"status": "queued", "job_id": str(job.id)})`
  - **Running:**
    `publish_job_event(job.id, {"status": "running", "job_id": str(job.id)})`
  - **Completed:**
    `publish_job_event(job.id, {"status": "completed", "job_id": str(job.id), "result": job.result})`
  - **Failed:**
    `publish_job_event(job.id, {"status": "failed", "job_id": str(job.id), "error": job.error_message})`

- **The End-to-End Real-Time Flow:**
  ```text
  1. Worker finishes running a job and publishes an event to Redis channel `job_events:{job_id}`.
  2. Client browser is connected via WebSocket (`/ws/jobs/{job_id}`).
  3. `start_redis_listener` in FastAPI catches the Redis message.
  4. Listener extracts the payload and invokes `connection_manager.broadcast_to_job()`.
  5. `ConnectionManager` sends the JSON result directly down the open WebSocket pipe to the client.
  ```

## 03/09/2026 — Level 6: Idempotency Keys & Exactly-Once Semantics

- **The Core Problem:**
  - An operation is **idempotent** if applying it multiple times produces the exact same result as applying it once.
  - Without idempotency, a network blip or double-click triggers a client retry that creates/runs two separate jobs in PostgreSQL and Celery for the same user action, corrupting DB state and duplicating work.

- **How We Solved It (`X-Idempotency-Key`):**
  - **Client-Side:**
    - The frontend generates a unique UUID (e.g., `crypto.randomUUID()`) when the user initiates an action.
    - It stores this key in a local variable and sends it as an HTTP header: `X-Idempotency-Key`.
    - If a network error occurs, the client's retry loop sends the **exact same key** on subsequent attempts.

  - **Server-Side (`app/services/idempotency.py` & `app/main.py`):**
    1. **Check & Distributed Lock (`check_or_lock`):**
       - When a request arrives, we check Redis key `idempotency:{key}`.
       - **If Key Exists:**
         - Value is `"IN_PROGRESS"` ➔ Another request is actively running! Return `("IN_PROGRESS", None)` ➔ API responds with **HTTP 409 Conflict**.
         - Value is a JSON string ➔ Previous request finished! Parse with `json.loads` and return `("COMPLETED", cached_data)` ➔ API returns the cached response immediately (0 database writes!).
       - **If Key Does Not Exist:**
         - Acquire atomic lock: `redis.set(key, "IN_PROGRESS", nx=True, ex=60)`.
         - If acquired: Return `("NEW", None)` ➔ API is authorized to execute the database creation/Celery enqueue.
         - If race condition occurs (`not acquired`): Another request beat us in that exact millisecond ➔ Return `("IN_PROGRESS", None)`.
    2. **Save Cached Response (`save_response`):**
       - Once the database/enqueue finishes, replace `"IN_PROGRESS"` with the serialized JSON response (`JobsResponse.model_validate(job).model_dump(mode="json")`).
       - Set TTL to 24 hours (`ex=86400`).

  - **Pydantic V2 ORM Serialization (`app/models/jobs.py`):**
    - Added `model_config = ConfigDict(from_attributes=True)` to `JobsResponse` so Pydantic can directly validate and extract attributes from SQLAlchemy `Job` ORM objects.

- **The End-to-End Idempotency Flow:**
  ```text
  Client (First Click) ────► POST /jobs [Key: AAA] ──► Locked "IN_PROGRESS" ──► Creates DB Row ──► Saves JSON in Redis ──► Returns Job
  Client (Network Retry) ──► POST /jobs [Key: AAA] ──► Finds Saved JSON in Redis ───────────────► Zero DB operations! ──► Returns Job
  Client (Double Click) ───► POST /jobs [Key: AAA] ──► Key is "IN_PROGRESS" ────────────────────► HTTP 409 Conflict!
  ```

---

## 04/09/2026 — Level 6: Distributed Rate Limiting (Token Bucket + Redis Lua)

- **The Problem:**
  - Idempotency protects against retrying the *same* request. But what if a client enters an infinite loop or spams 5,000 *different* requests per second?
  - Without API throttling, the PostgreSQL connection pool collapses, Redis memory spikes, and workers get overwhelmed.
  - We need a gatekeeper to enforce a fair usage quota: **HTTP 429 Too Many Requests**.

---

### 1. The Algorithm: Token Bucket 🪣
- **Capacity ($B = 10$):** Maximum number of tokens the bucket can hold (burst limit).
- **Refill Rate ($r = 1.0$ token/sec):** Tokens are continuously added back as time elapses.
- **Cost:** Each request costs **1 token**.

```text
               💧 Continuous Refill (+1 token / sec up to capacity 10)
                 │
                 ▼
          ┌─────────────┐
          │  ● ● ● ● ●  │  Bucket holds up to 10 tokens (Burst limit)
          │  ● ● ● ● ●  │
          └──────┬──────┘
                 │
       Incoming HTTP Request arrives:
       ├── Has tokens (tokens >= 1)?
       │   └── Deduct 1 token ➔ Return 200 OK! ✅
       └── Bucket empty (tokens < 1)?
           └── Block immediately ➔ Return 429 Too Many Requests! 🛑
```

---

### 2. The Concurrency Race Condition & Redis Lua Solution 📜⚡

- **Why Not Calculate in Python?**
  - If 10 requests hit 3 FastAPI instances at the exact same millisecond when 1 token is left:
    - All 10 read `tokens = 1` from Redis.
    - All 10 subtract 1 in Python and save `tokens = 0`.
    - **All 10 requests get allowed through!** (Rate limit breached due to check-then-act race condition).
- **The Lua Script Solution:**
  - Redis executes Lua scripts **single-threaded and atomically** directly inside memory in $0.05\text{ms}$.
  - No other Redis command can interrupt while the script calculates time elapsed, refills tokens, and deducts a token. Zero race conditions across multiple API instances!

---

### 3. FastAPI Global Gatekeeper Architecture

- Implemented in `app/main.py` using `app = FastAPI(dependencies=[Depends(rate_limit)])`.
- **Gatekeeper vs Data Provider:**
  - `rate_limit` is a **Gatekeeper**: Runs before route logic to allow or abort (`429`). Does not inject variables into routes.
  - `get_db` and `cache` are **Data Providers**: Injected into specific endpoints (`repo: JobRepo`) to avoid opening useless DB connections on static/cached routes.

---

### 4. Bugs & Errors Faced During Implementation 🛠️

1. **Lua Syntax Traps:**
   - *Error:* `tokens = nil` (single `=` is assignment) ➔ *Fix:* In Lua equality is `==` (`if tokens == nil`).
   - *Error:* `tokens += ...` and `tokens -= 1` ➔ *Fix:* Lua has no `+=` or `-=`. Must write `tokens = tokens - 1`.
   - *Error:* `return "1"` (string) ➔ *Fix:* In Python `"1" == 1` is `False`. Lua must return integer `1` or `0`.
   - *Error:* `HGET` with multiple fields ➔ *Fix:* `HGET` only takes 1 field. Used `HMGET` for multiple hash fields.

2. **The Rate Limiter Throttled the Test Suite! (8 Tests Failed with 429):**
   - *Error:* Running 22 tests in 2 seconds generated >25 requests under the default IP `"testclient"`, exhausting the 10 tokens and causing all subsequent tests to fail with `429`.
   - *Fix:* Added test runner bypass:
     `if client_ip == "testclient" and "X-Forwarded-For" not in connection.headers: return`
     This allows general unit tests to run unthrottled, while `test_rate_limit()` specifies `X-Forwarded-For: 192.168.1.99` to strictly verify the 429 behavior.

3. **WebSocket Route Crashed (`TypeError: rate_limit() missing 'request'`):**
   - *Error:* Global `FastAPI(dependencies=[...])` applies to WebSocket routes too (`/ws/jobs/{id}`). WebSockets receive a `WebSocket` object, not an HTTP `Request` object.
   - *Fix:* Changed parameter type to **`HTTPConnection`** (`from starlette.requests import HTTPConnection`), which is the common base class for both `Request` and `WebSocket`.



