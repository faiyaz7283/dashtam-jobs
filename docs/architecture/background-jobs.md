# Background Jobs Architecture

## Overview

### Purpose

The **Dashtam Background Jobs** infrastructure provides a centralized, async-native task queue system for all Dashtam applications. It enables deferred execution, scheduled jobs, and long-running tasks without blocking API responses or TUI interactions.

**Key Benefits**:

- **Single source of truth** — All job definitions in one place (`dashtam-jobs`)
- **Zero drift** — API, Terminal, and future apps share identical job implementations
- **Async-native** — Built on Python's asyncio, matches Dashtam's async architecture
- **Type-safe** — Full PEP-612 type hints with autocomplete support
- **Fault-tolerant** — Acknowledgements, retries, and persistent Redis queues
- **Observable** — Job status tracking, execution times, error logging

### Problem Statement

**Without Background Jobs**:

- **Blocking operations** (Gap ⚠️): Long-running tasks block HTTP responses
- **No scheduling** (Gap ⚠️): Cannot run periodic tasks (token expiry checks)
- **Tight coupling** (Gap ⚠️): Sync operations must complete before response
- **Poor UX** (Gap ⚠️): Users wait for operations that could run asynchronously
- **No retry logic** (Gap ⚠️): Failed operations must be manually retried

**Example**: Checking for expiring provider tokens requires a periodic background job. Without this infrastructure, we cannot proactively notify users of expiring credentials.

### Solution

**Centralized TaskIQ-based job service**:

```text
~/dashtam/
├── api/                    # Producer (enqueues jobs)
├── terminal/               # Producer (enqueues jobs)
├── jobs/                   # Centralized job service (SSOT)
│   ├── src/dashtam_jobs/
│   │   ├── broker.py       # Shared broker configuration
│   │   ├── tasks/          # All job definitions
│   │   └── scheduler.py    # Cron/scheduled tasks
│   └── docker-compose.yml  # Worker service
└── docker-services/
    └── redis               # Shared message broker
```

**Benefits**:

- ✅ Jobs defined once, used by all applications
- ✅ Single worker service to deploy and monitor
- ✅ Consistent retry/scheduling behavior across apps
- ✅ Easy to test jobs in isolation
- ✅ Horizontal scaling via worker replicas

---

## Framework Selection

### Why TaskIQ

After evaluating async-native Python task queue frameworks, **TaskIQ** was selected over alternatives:

| Factor | TaskIQ | ARQ | Celery |
| -------- | -------- | ----- | -------- |
| **Maintenance Status** | ✅ Actively maintained | ⚠️ Maintenance-only | ✅ Active |
| **Async-Native** | ✅ Full async | ✅ Full async | ⚠️ Sync default |
| **FastAPI Integration** | ✅ `taskiq-fastapi` | ❌ Manual | ⚠️ Complex |
| **Dependency Injection** | ✅ `TaskiqDepends()` | ❌ `ctx` dict | ❌ None |
| **Type Hints** | ✅ PEP-612 | ⚠️ Basic | ⚠️ Basic |
| **Broker Flexibility** | ✅ Redis, RabbitMQ, Kafka | ❌ Redis only | ✅ Multiple |
| **Python 3.14+** | ✅ Supported | ✅ Supported | ✅ Supported |

**Key Decision Factors**:

1. **Active maintenance** — ARQ is in maintenance-only mode (GitHub issue #510)
2. **FastAPI-like DI** — `TaskiqDepends()` mirrors FastAPI's `Depends()`, consistent with Dashtam patterns
3. **Type safety** — PEP-612 enables full autocomplete and type checking
4. **Broker flexibility** — Redis now, option to add RabbitMQ/Kafka later

### TaskIQ Components

**Required packages**:

```toml
[project.dependencies]
taskiq = ">=0.19.0"
taskiq-redis = ">=1.2.0"
```

**Optional packages**:

```toml
[project.optional-dependencies]
fastapi = ["taskiq-fastapi>=0.4.0"]  # FastAPI dependency reuse
```

---

## Architecture

### Centralized vs Per-App Workers

Two architectural patterns were evaluated:

**Option A: Per-App Workers** — Each app (API, Terminal) runs its own worker.

- ✅ Isolation (one app's job failures don't affect others)
- ❌ Code duplication (broker config, utilities repeated)
- ❌ Drift risk (patterns evolve independently)
- ❌ No shared jobs (same job duplicated if needed by both apps)

**Option B: Centralized Service** — Single `dashtam-jobs` service handles all jobs.

- ✅ SSOT (jobs defined once)
- ✅ Zero drift (all apps use same implementation)
- ✅ Shared jobs (token check, sync jobs usable by any app)
- ✅ Easier monitoring (one worker to observe)
- ⚠️ Requires worker redundancy (run multiple replicas)

**Decision**: Centralized service (Option B) aligns with Dashtam's SSOT philosophy.

### Repository Structure

```text
dashtam-jobs/
├── src/dashtam_jobs/
│   ├── __init__.py
│   ├── broker.py               # Broker configuration
│   ├── scheduler.py            # Scheduler configuration
│   ├── core/                   # Core utilities (config-driven)
│   │   ├── __init__.py
│   │   ├── settings.py         # Pydantic Settings (env-driven, NO hardcoding)
│   │   └── logging.py          # Structured logging configuration
│   ├── events/                 # Domain events emitted by jobs
│   │   ├── __init__.py
│   │   └── provider.py         # Provider-related events
│   ├── tasks/                  # Job definitions by domain
│   │   ├── __init__.py         # Re-exports all tasks
│   │   └── tokens.py           # Token-related jobs
│   ├── infrastructure/         # External integrations
│   │   ├── __init__.py
│   │   ├── database.py         # Database class with session management
│   │   └── repositories/       # Thin repository implementations
│   │       └── provider_connection.py
│   └── middlewares/            # TaskIQ middlewares
│       ├── __init__.py
│       └── logging.py          # Job execution logging
├── compose/                    # Docker Compose files (per environment)
│   ├── docker-compose.dev.yml
│   ├── docker-compose.test.yml
│   └── docker-compose.ci.yml
├── docker/
│   └── Dockerfile              # Multi-stage build
├── docs/
│   └── architecture/
│       └── background-jobs.md  # This document
├── tests/
│   ├── unit/                   # Job logic tests
│   └── integration/            # Broker integration tests
├── env/
│   ├── .env.dev.example        # Development template
│   ├── .env.test.example       # Test template
│   └── .env.ci.example         # CI template
├── pyproject.toml
├── Makefile
└── WARP.md                     # Project-specific rules
```

**Key Simplifications**:

- No `domain/` directory — events are simple dataclasses, complex logic lives in dashtam-api
- No `registry.py` — TaskIQ's `@broker.task` decorator handles registration
- No `result.py` — jobs return simple dicts, not Result types (API handles that)

### Data Flow

```text
┌────────────────────────────────────────────────────────────────────┐
│                           PRODUCERS                                │
├────────────────────────────────────────────────────────────────────┤
│                                                                    │
│  ┌─────────────┐          ┌─────────────┐          ┌─────────────┐ │
│  │  Dashtam    │          │  Dashtam    │          │   Future    │ │
│  │    API      │          │  Terminal   │          │    Apps     │ │
│  └──────┬──────┘          └──────┬──────┘          └──────┬──────┘ │
│         │                        │                        │        │
│         │  await task.kiq()      │  await task.kiq()      │        │
│         │                        │                        │        │
└─────────┼────────────────────────┼────────────────────────┼────────┘
          │                        │                        │
          ▼                        ▼                        ▼
┌────────────────────────────────────────────────────────────────────┐
│                         MESSAGE BROKER                             │
├────────────────────────────────────────────────────────────────────┤
│                                                                    │
│                     ┌───────────────────┐                          │
│                     │   Redis Queue     │                          │
│                     │  (Persistent)     │                          │
│                     └─────────┬─────────┘                          │
│                               │                                    │
└───────────────────────────────┼────────────────────────────────────┘
                                │
                                ▼
┌────────────────────────────────────────────────────────────────────┐
│                          CONSUMERS                                 │
├────────────────────────────────────────────────────────────────────┤
│                                                                    │
│  ┌───────────────────────────────────────────────────────────────┐ │
│  │                    dashtam-jobs Worker(s)                     │ │
│  │                                                               │ │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐            │ │
│  │  │   Token     │  │    Sync     │  │Notification │            │ │
│  │  │   Tasks     │  │    Tasks    │  │   Tasks     │            │ │
│  │  └─────────────┘  └─────────────┘  └─────────────┘            │ │
│  │                                                               │ │
│  └───────────────────────────────────────────────────────────────┘ │
│                                                                    │
│  Note: Run multiple worker replicas for redundancy                 │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘
```

---

## Architecture Patterns

### Why Simpler Than dashtam-api?

The `dashtam-jobs` service has a **different responsibility profile** than `dashtam-api`:

| Concern | dashtam-api | dashtam-jobs |
| --------- | ------------- | --------------- |
| **Primary Role** | Handle HTTP requests, validate input, return responses | Execute background tasks |
| **User Interaction** | Direct (API endpoints) | Indirect (via queue) |
| **Request Complexity** | High (auth, validation, routing, responses) | Low (task receives pre-validated data) |
| **Domain Logic** | Complex (business rules, aggregates) | Focused (single-purpose tasks) |
| **State Management** | Complex (sessions, transactions) | Simple (task-scoped) |

**Result**: Jobs benefit from structure but don't need the full Hexagonal/CQRS complexity of an API.

### Patterns Used in dashtam-jobs

#### 1. Task Registration (TaskIQ Built-in)

**No separate registry needed.** TaskIQ's `@broker.task` decorator automatically registers tasks:

```python
# src/dashtam_jobs/tasks/tokens.py

@broker.task(
    retry_on_error=True,
    max_retries=3,
    timeout=300,
    labels={"category": "provider", "schedule": "*/15 * * * *"},
)
async def check_expiring_tokens(
    context: Annotated[Context, TaskiqDepends()],
) -> dict[str, int]:
    """Check for provider tokens expiring within 24 hours.
    
    Runs every 15 minutes via scheduler. Emits ProviderTokenExpiringSoon
    domain events for each connection with expiring tokens.
    
    Returns:
        Dict with counts: {"checked": N, "expiring": M, "notified": K}
    """
    ...
```

**Why no separate JOB_REGISTRY?**

- TaskIQ already tracks registered tasks via `broker.tasks`
- Metadata via `labels` parameter and docstrings
- Avoids duplication (define task + add to registry)
- API can query `broker.tasks` for job discovery endpoints

**Compliance tests** verify expected tasks are registered:

```python
def test_all_expected_tasks_registered():
    """Verify all expected jobs are registered with broker."""
    expected = {"check_expiring_tokens", "sync_accounts", "send_notification"}
    registered = {name for name in broker.tasks.keys()}
    assert expected.issubset(registered)
```

#### 2. Simplified Layered Architecture

Not full Hexagonal, but clear separation:

```text
┌─────────────────────────────────────────────────────────┐
│                      TASKS LAYER                        │
│  (Job definitions - what to do)                         │
│  src/dashtam_jobs/tasks/                                │
│  - @broker.task decorated async functions               │
│  - Docstrings describe purpose & behavior               │
│  - Labels provide metadata (category, schedule)         │
├─────────────────────────────────────────────────────────┤
│                   INFRASTRUCTURE LAYER                  │
│  (How to access external resources)                     │
│  src/dashtam_jobs/infrastructure/                       │
│  - database.py (session factory)                        │
│  - repositories/ (thin data access)                     │
├─────────────────────────────────────────────────────────┤
│                      CORE LAYER                         │
│  (Configuration & utilities - NO hardcoding)            │
│  src/dashtam_jobs/core/                                 │
│  - settings.py (Pydantic Settings, env-driven)          │
│  - logging.py (structured logging config)               │
└─────────────────────────────────────────────────────────┘
```

**Why not full Hexagonal?**

- Jobs don't have "ports" (no HTTP, no CLI commands)
- Single entry point (TaskIQ worker)
- Domain logic lives in dashtam-api; jobs orchestrate, not implement
- Domain events defined in dashtam-api; jobs import and publish them

#### 3. Config-Driven Settings (No Hardcoding)

**Same principle as dashtam-api**: All configuration via environment variables.

```python
# src/dashtam_jobs/core/settings.py

from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    """Application settings loaded from environment.
    
    All values come from environment variables.
    No hardcoded defaults for environment-specific values.
    """
    
    # Required - no defaults (must be set in env)
    redis_url: str
    database_url: str
    
    # Optional with sensible defaults
    job_result_ttl: int = 86400  # 24 hours
    worker_concurrency: int = 10
    log_level: str = "INFO"
    
    # Token expiry check configuration
    token_expiry_threshold_hours: int = 24
    token_check_cron: str = "*/15 * * * *"
    
    model_config = SettingsConfigDict(
        env_file="env/.env.dev",
        env_file_encoding="utf-8",
        extra="ignore",
    )

@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance (lazy-loaded)."""
    return Settings()

# Proxy for convenient attribute access
class _SettingsProxy:
    def __getattr__(self, name: str) -> object:
        return getattr(get_settings(), name)

settings = _SettingsProxy()
```

**env/.env.dev.example** (template, committed — one per environment):

```bash
# Redis Configuration (jobs-specific instance)
JOBS_REDIS_PORT=6381
REDIS_URL=redis://redis:6379/0

# Database Configuration (connects to dashtam-api's database)
DATABASE_URL=postgresql+asyncpg://dashtam_user:password@dashtam-dev-postgres:5432/dashtam

# Optional (defaults shown)
JOB_RESULT_TTL=86400
WORKER_CONCURRENCY=10
LOG_LEVEL=DEBUG
TOKEN_EXPIRY_THRESHOLD_HOURS=24
TOKEN_CHECK_CRON=*/15 * * * *
```

**Environment-specific files**:

- `env/.env.dev.example` → Development
- `env/.env.test.example` → Testing  
- `env/.env.ci.example` → CI/CD

**Usage in tasks** (config, not hardcoded values):

```python
from dashtam_jobs.core.settings import settings

@broker.task
async def check_expiring_tokens(context: Context = TaskiqDepends()) -> dict:
    # Use config values, never hardcode
    expiring = await repo.find_expiring_soon(
        hours=settings.token_expiry_threshold_hours
    )
    ...
```

#### 4. Dependency Injection via TaskIQ State

**Where does DI happen?**

| Context | Where DI Happens | How |
| --------- | ------------------ | ----- |
| **Producer (API/Terminal)** | Not needed | Just calls `task.kiq()` - no dependencies required |
| **Worker (dashtam-jobs)** | Worker startup | `TaskiqState` holds shared resources |
| **Task Execution** | Via `TaskiqDepends()` | Task receives context with injected dependencies |

**Conceptual Flow**:

```text
1. WORKER STARTS
   └── @broker.on_event(WORKER_STARTUP) runs
   └── Creates: db_engine, redis_pool, event_bus
   └── Stores in: TaskiqState

2. TASK EXECUTES
   └── TaskIQ injects Context (contains TaskiqState)
   └── Task accesses: context.state.db_engine
   └── Creates session, does work, closes session

3. WORKER STOPS
   └── @broker.on_event(WORKER_SHUTDOWN) runs
   └── Closes: db_engine, redis_pool
```

**Code Pattern**:

```python
# src/dashtam_jobs/infrastructure/database.py
class Database:
    """Database connection and session management for jobs worker."""
    
    def __init__(self, database_url: str) -> None:
        self.engine = create_async_engine(
            database_url,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=10,
        )
        self.async_session = async_sessionmaker(self.engine, expire_on_commit=False)
    
    @asynccontextmanager
    async def get_session(self) -> AsyncGenerator[AsyncSession]:
        async with self.async_session() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
    
    async def close(self) -> None:
        await self.engine.dispose()
```

```python
# src/dashtam_jobs/broker.py - Worker startup
@broker.on_event(TaskiqEvents.WORKER_STARTUP)
async def startup(state: TaskiqState) -> None:
    """Initialize resources shared across all task executions."""
    from dashtam_jobs.infrastructure.database import Database
    state.database = Database(_settings.database_url)

@broker.on_event(TaskiqEvents.WORKER_SHUTDOWN)
async def shutdown(state: TaskiqState) -> None:
    """Clean up resources when worker shuts down."""
    if hasattr(state, "database") and state.database is not None:
        await state.database.close()
```

```python
# Task uses Database via context
@broker.task
async def check_expiring_tokens(
    context: Annotated[Context, TaskiqDepends()],
) -> dict[str, int]:
    """Access database via context.state.database."""
    async with context.state.database.get_session() as session:
        repo = ProviderConnectionRepository(session)
        # ... do work
```

#### 5. Code Reuse Strategy

**Problem**: Jobs may need logic that exists in dashtam-api (repositories, domain models).

**Options**:

| Approach | Pros | Cons | When to Use |
| ---------- | ------ | ------ | ------------- |
| **Duplicate code** | Simple, independent | Drift risk | Avoid |
| **Import from API** | No duplication | Coupling, import complexity | If API is a dependency |
| **Shared package** | Clean, explicit | Another package to maintain | For significant shared code |
| **Thin wrappers** | Jobs stay simple | Some duplication | **Recommended** |

**Recommended Approach - Thin Wrappers**:

Jobs should be **orchestrators**, not implementers:

```python
# BAD: Job implements complex logic
@broker.task
async def check_expiring_tokens(context: Context = TaskiqDepends()) -> None:
    # 50 lines of repository queries, business logic, etc.
    ...

# GOOD: Job orchestrates, delegates to focused functions
@broker.task
async def check_expiring_tokens(context: Context = TaskiqDepends()) -> dict:
    """Orchestrate token expiry check.
    
    1. Query expiring connections
    2. Emit events for each
    3. Return summary
    """
    async with AsyncSession(context.state.db_engine) as session:
        # Thin repository - just the query we need
        repo = ProviderConnectionRepository(session)
        expiring = await repo.find_expiring_soon(hours=24)
        
        # Emit events (API's SSE handler will pick these up)
        for conn in expiring:
            await context.state.event_bus.publish(
                ProviderTokenExpiringSoon(connection_id=conn.id, ...)
            )
        
        return {"checked": len(expiring), "notified": len(expiring)}
```

---

## Core Components

### 1. Broker Configuration

**Purpose**: Central broker instance connecting to Redis.

**Location**: `src/dashtam_jobs/broker.py`

```python
from taskiq_redis import ListQueueBroker, RedisAsyncResultBackend
from dashtam_jobs.core.settings import get_settings
from dashtam_jobs.middlewares.logging import JobLoggingMiddleware

_settings = get_settings()

# Broker for task queuing with middleware
broker = (
    ListQueueBroker(
        url=_settings.redis_url,
        queue_name="dashtam:jobs",
    )
    .with_result_backend(
        RedisAsyncResultBackend(
            redis_url=_settings.redis_url,
            result_ex_time=_settings.job_result_ttl,
        )
    )
    .with_middlewares(
        JobLoggingMiddleware(),
    )
)
```

**Configuration**:

- `ListQueueBroker` — Uses Redis LIST for FIFO ordering
- `RedisAsyncResultBackend` — Stores job results in Redis
- `JobLoggingMiddleware` — Structured logging for all job executions
- `result_ex_time` — Result TTL from settings (prevents unbounded growth)

### 2. Task Definition

**Purpose**: Define executable background jobs.

**Location**: `src/dashtam_jobs/tasks/`

**Pattern**:

```python
from dashtam_jobs.broker import broker

@broker.task(retry_on_error=True, max_retries=3)
async def check_expiring_tokens() -> dict[str, int]:
    """Check for provider tokens expiring within threshold.
    
    Returns:
        Dict with counts: {"checked": N, "expiring": M, "notified": K}
    """
    # Implementation here
    ...
```

**Task Decorator Options**:

| Option | Type | Description |
| -------- | ------ | ------------- |
| `retry_on_error` | `bool` | Enable automatic retry on exception |
| `max_retries` | `int` | Maximum retry attempts |
| `timeout` | `float` | Task timeout in seconds |
| `labels` | `dict` | Custom metadata for the task |

### 3. Scheduler Configuration

**Purpose**: Define cron-scheduled and interval-based jobs.

**Location**: `src/dashtam_jobs/scheduler.py`

```python
from taskiq import TaskiqScheduler
from taskiq_redis import RedisScheduleSource
from dashtam_jobs.broker import broker
from dashtam_jobs.settings import settings

# Schedule source stores scheduled tasks in Redis
schedule_source = RedisScheduleSource(settings.redis_url)

# Scheduler manages execution timing
scheduler = TaskiqScheduler(
    broker=broker,
    sources=[schedule_source],
)
```

**Scheduling Tasks**:

```python
from dashtam_jobs.tasks.tokens import check_expiring_tokens

# Cron-based (every 15 minutes)
await check_expiring_tokens.schedule_by_cron(
    schedule_source,
    "*/15 * * * *",
)

# Time-based (run at specific time)
await some_task.schedule_by_time(
    schedule_source,
    datetime.now(UTC) + timedelta(hours=1),
    arg1, arg2="value",
)
```

### 4. Worker Entry Point

**Purpose**: CLI entry point for running workers.

**Location**: `src/dashtam_jobs/worker.py` (or via CLI)

**Running Workers**:

```bash
# Basic worker
taskiq worker dashtam_jobs.broker:broker

# With acknowledgement safety
taskiq worker dashtam_jobs.broker:broker --ack-type when_executed

# With concurrency limit
taskiq worker dashtam_jobs.broker:broker --max-async-tasks 10

# With scheduler (for cron jobs)
taskiq scheduler dashtam_jobs.scheduler:scheduler
```

### 5. Dependency Injection

**Purpose**: Inject dependencies (database, cache, etc.) into tasks.

**Pattern**:

```python
from typing import Annotated
from taskiq import Context, TaskiqDepends, TaskiqEvents, TaskiqState
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

# Worker startup: initialize shared resources
@broker.on_event(TaskiqEvents.WORKER_STARTUP)
async def startup(state: TaskiqState) -> None:
    state.db_engine = create_async_engine(settings.database_url)
    state.redis = await aioredis.from_url(settings.redis_url)

# Worker shutdown: cleanup resources
@broker.on_event(TaskiqEvents.WORKER_SHUTDOWN)
async def shutdown(state: TaskiqState) -> None:
    await state.db_engine.dispose()
    await state.redis.close()

# Task with dependency injection
@broker.task
async def process_data(
    data_id: str,
    context: Annotated[Context, TaskiqDepends()],
) -> None:
    async with AsyncSession(context.state.db_engine) as session:
        # Use session for database operations
        ...
```

---

## Job Lifecycle

### Enqueuing Jobs

**From Producer (API/Terminal)**:

```python
from dashtam_jobs.tasks.sync import sync_accounts

# Fire-and-forget
await sync_accounts.kiq(connection_id=str(conn_id), user_id=str(user_id))

# With result tracking
task = await sync_accounts.kiq(connection_id=str(conn_id), user_id=str(user_id))
result = await task.wait_result(timeout=30)

if result.is_err:
    logger.error(f"Sync failed: {result.error}")
else:
    logger.info(f"Synced {result.return_value['account_count']} accounts")
```

### Job Execution Flow

```text
1. Producer calls task.kiq()
   └── Job serialized and pushed to Redis queue

2. Worker pulls job from queue
   └── Acknowledged based on --ack-type setting

3. Worker executes task function
   └── Dependencies injected via TaskiqDepends

4. On success:
   └── Result stored in result backend
   └── Job removed from queue

5. On failure:
   └── If retry_on_error: Re-enqueue with incremented try count
   └── If max_retries exceeded: Mark as failed, store error
```

### Acknowledgement Modes

| Mode | When Acknowledged | Use Case |
| ---- | ----------------- | -------- |
| `when_received` | Immediately on receipt | Fire-and-forget, idempotent jobs |
| `when_executed` | After task completes | **Recommended default** |
| `when_saved` | After result saved | Critical jobs requiring result persistence |

**Recommendation**: Use `--ack-type when_executed` for safety.

---

## Fault Tolerance

### Worker Failure Recovery

**Scenario**: Worker crashes mid-execution.

**With `--ack-type when_executed`**:

1. Job remains in Redis queue (not acknowledged)
2. Worker restarts (or another replica picks up)
3. Job re-executed from beginning

**Design Consideration**: Jobs should be **idempotent** where possible.

```python
@broker.task
async def process_payment(payment_id: str, context: Context = TaskiqDepends()) -> None:
    async with AsyncSession(context.state.db_engine) as session:
        # Idempotency check: skip if already processed
        existing = await session.get(Payment, payment_id)
        if existing and existing.status == "completed":
            return  # Already done, skip
        
        # Process payment...
```

### Retry Configuration

```python
from taskiq import SimpleRetryMiddleware

broker = ListQueueBroker(...).with_middlewares(
    SimpleRetryMiddleware(default_retry_count=3),
)

# Per-task retry override
@broker.task(retry_on_error=True, max_retries=5)
async def flaky_external_api_call() -> None:
    # Will retry up to 5 times on exception
    ...
```

### Worker Redundancy

**Production Configuration**:

```yaml
# docker-compose.yml
services:
  jobs-worker:
    image: dashtam-jobs
    command: taskiq worker dashtam_jobs.broker:broker --ack-type when_executed
    deploy:
      replicas: 2  # Minimum 2 for redundancy
    restart: unless-stopped
    depends_on:
      - redis
```

---

## Job Flexibility

### Delayed Execution

```python
from datetime import datetime, timedelta, UTC

# Execute in 5 minutes
await my_task.schedule_by_time(
    schedule_source,
    datetime.now(UTC) + timedelta(minutes=5),
    arg1="value",
)
```

### Cron Scheduling

```python
# Every hour at minute 0
await hourly_task.schedule_by_cron(schedule_source, "0 * * * *")

# Every day at 2:30 AM UTC
await daily_task.schedule_by_cron(schedule_source, "30 2 * * *")

# Every Monday at 9 AM
await weekly_task.schedule_by_cron(schedule_source, "0 9 * * 1")
```

### Cancellation

```python
# Schedule returns a handle
schedule = await my_task.schedule_by_time(
    schedule_source,
    future_time,
    arg="value",
)

# Cancel before execution
await schedule.unschedule()
```

### Job Status Checking

```python
task = await my_task.kiq(arg="value")

# Wait with timeout
result = await task.wait_result(timeout=30)

# Check result
if result.is_err:
    print(f"Error: {result.error}")
    print(f"Logs: {result.log}")
else:
    print(f"Success: {result.return_value}")
    print(f"Execution time: {result.execution_time}s")
```

---

## Integration with Producers

### API Integration

**FastAPI producer setup**:

```python
# src/core/container/jobs.py
from dashtam_jobs.broker import broker

async def get_jobs_broker() -> AsyncGenerator[Broker, None]:
    """Request-scoped broker for job enqueuing."""
    if not broker.is_worker_process:
        await broker.startup()
    yield broker

# Dependency for FastAPI endpoints
JobsBroker = Annotated[Broker, Depends(get_jobs_broker)]
```

**Usage in endpoint**:

```python
@router.post("/connections/{connection_id}/sync")
async def trigger_sync(
    connection_id: UUID,
    current_user: CurrentUser,
) -> SyncResponse:
    from dashtam_jobs.tasks.sync import sync_accounts
    
    task = await sync_accounts.kiq(
        connection_id=str(connection_id),
        user_id=str(current_user.id),
    )
    
    return SyncResponse(job_id=task.task_id, status="queued")
```

### Terminal Integration

**TUI producer setup**:

```python
# src/dashtam_terminal/infrastructure/jobs/client.py
from dashtam_jobs.broker import broker

class JobClient:
    """Client for enqueuing background jobs from Terminal."""
    
    async def startup(self) -> None:
        await broker.startup()
    
    async def shutdown(self) -> None:
        await broker.shutdown()
    
    async def enqueue_sync(self, connection_id: UUID, user_id: UUID) -> str:
        from dashtam_jobs.tasks.sync import sync_accounts
        task = await sync_accounts.kiq(
            connection_id=str(connection_id),
            user_id=str(user_id),
        )
        return task.task_id
```

---

## Testing

### Unit Testing Jobs

```python
import pytest
from taskiq import InMemoryBroker
from dashtam_jobs.tasks.tokens import check_expiring_tokens

@pytest.fixture
def test_broker():
    """Use in-memory broker for unit tests."""
    return InMemoryBroker()

@pytest.mark.anyio
async def test_check_expiring_tokens(test_broker, mock_db_session):
    # Override broker for test
    result = await check_expiring_tokens.fn()  # Direct call
    
    assert result["checked"] >= 0
    assert "expiring" in result
```

### Integration Testing

```python
@pytest.mark.integration
@pytest.mark.anyio
async def test_job_enqueue_and_execute(redis_broker):
    """Test full job lifecycle with real Redis."""
    from dashtam_jobs.tasks.sync import sync_accounts
    
    task = await sync_accounts.kiq(
        connection_id="test-id",
        user_id="test-user",
    )
    
    result = await task.wait_result(timeout=10)
    assert not result.is_err
```

---

## Monitoring & Observability

Monitoring background jobs requires visibility into:

1. **Job Health**: Are workers running? Processing jobs?
2. **Job Status**: What's queued? Running? Completed? Failed?
3. **Job Results**: What did completed jobs return? Any errors?
4. **Metrics**: Execution times, retry counts, queue depths
5. **Logs**: Detailed execution traces for debugging

### Monitoring Architecture

```text
┌─────────────────────────────────────────────────────────────────────┐
│                        MONITORING CONSUMERS                         │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────────────────┐  │
│  │  Dashtam    │    │  Dashtam    │    │   External Tools        │  │
│  │  Terminal   │    │    API      │    │   (Grafana, etc.)       │  │
│  │  (TUI)      │    │  /jobs/*    │    │                         │  │
│  └──────┬──────┘    └──────┬──────┘    └───────────┬─────────────┘  │
│         │                  │                       │                │
└─────────┼──────────────────┼───────────────────────┼────────────────┘
          │                  │                       │
          │ Query            │ Expose                │ Scrape
          │ Redis            │ REST                  │ Metrics
          │                  │                       │
          ▼                  ▼                       ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         DATA SOURCES                                │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌───────────────┐  ┌───────────────┐  ┌───────────────────────┐    │
│  │    Redis      │  │   Job Logs    │  │   Prometheus          │    │
│  │  - Queue      │  │  (Structured) │  │   Metrics (optional)  │    │
│  │  - Results    │  │               │  │                       │    │
│  │  - Schedules  │  │               │  │                       │    │
│  └───────────────┘  └───────────────┘  └───────────────────────┘    │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### Implemented: dashtam-api Job Monitoring

**Communication**: API and Jobs share Redis — no code dependency between repos.

```text
dashtam-api (JobsMonitor) ──── Redis (shared) ──── dashtam-jobs (TaskIQ Broker)
```

**Endpoints in dashtam-api**:

| Endpoint | Auth | Purpose |
| -------- | ---- | ------- |
| `GET /health/jobs` | None | Simple status for load balancers |
| `GET /api/v1/admin/jobs` | Admin | Detailed status for admin dashboard |

**Implementation** (`src/infrastructure/jobs/monitor.py`):

```python
class JobsMonitor:
    """Monitor background jobs via shared Redis.
    
    Uses Railway-Oriented Programming (ROP) for error handling.
    """
    
    def __init__(self, redis_url: str, queue_name: str = "dashtam:jobs") -> None:
        self._redis_url = redis_url
        self._queue_name = queue_name
        self._redis: redis.asyncio.Redis | None = None
    
    async def get_status(self) -> Result[JobsStatus, InfrastructureError]:
        """Get current jobs system status.
        
        Returns:
            Result containing JobsStatus or InfrastructureError.
        """
        try:
            redis_client = await self._get_redis()
            
            # Check Redis connectivity
            await redis_client.ping()
            redis_connected = True
            
            # Get queue depth
            queue_depth = await redis_client.llen(self._queue_name)
            
            return Ok(JobsStatus(
                redis_connected=redis_connected,
                queue_depth=queue_depth,
                status="healthy" if redis_connected else "degraded",
            ))
        except Exception as e:
            return Err(InfrastructureError(
                code=InfrastructureErrorCode.CONNECTION_ERROR,
                message=f"Failed to connect to jobs Redis: {e}",
            ))
```

**Configuration** (`src/core/config.py`):

```python
# Jobs monitoring (optional - falls back to REDIS_URL)
jobs_redis_url: str | None = None
jobs_queue_name: str = "dashtam:jobs"
```

### Future: Terminal Direct Redis Access

**When useful**: For TUI dashboards showing real-time job status without API round-trip.

**Terminal component**:

```python
# src/dashtam_terminal/infrastructure/jobs/monitor.py

class TerminalJobMonitor:
    """Direct Redis access for job monitoring in TUI.
    
    Connects to same Redis as job workers. Read-only operations.
    """
    
    def __init__(self, redis_url: str):
        self._redis_url = redis_url
        self._redis: Redis | None = None
    
    async def connect(self) -> None:
        self._redis = await aioredis.from_url(self._redis_url)
    
    async def get_queue_depth(self) -> int:
        return await self._redis.llen("dashtam:jobs")
    
    async def get_recent_completions(self, limit: int = 10) -> list[dict]:
        """Get recently completed jobs for display."""
        # Scan for result keys
        ...
```

**TUI Widget**:

```python
# src/dashtam_terminal/presentation/tui/widgets/job_status.py

class JobStatusWidget(Widget):
    """Real-time job queue status display."""
    
    def compose(self) -> ComposeResult:
        yield Static("Jobs", id="title")
        yield Static("", id="queue-depth")
        yield Static("", id="recent-jobs")
    
    async def on_mount(self) -> None:
        self.set_interval(5, self.refresh_status)  # Refresh every 5s
    
    async def refresh_status(self) -> None:
        depth = await self.monitor.get_queue_depth()
        self.query_one("#queue-depth").update(f"Queued: {depth}")
```

### Option 3: TaskIQ Dashboard (Optional Add-on)

TaskIQ has a community dashboard package that provides a web UI:

```bash
uv add taskiq-dashboard
```

```python
# Run dashboard
taskiq-dashboard --broker dashtam_jobs.broker:broker
```

**Pros**: Ready-made UI, no custom development
**Cons**: Separate service, different auth system

**Recommendation**: Use API endpoints + Terminal widgets as primary monitoring; consider TaskIQ Dashboard for debugging.

### Logging Strategy

All job execution is logged with structlog in JSON format:

```python
# src/dashtam_jobs/middlewares/logging.py

class JobLoggingMiddleware(TaskiqMiddleware):
    """Structured logging for all job executions."""
    
    async def pre_execute(self, message: TaskiqMessage) -> TaskiqMessage:
        """Log when job starts."""
        logger.info(
            "job_started",
            job_id=message.task_id,
            task_name=message.task_name,
            args=str(message.args)[:100],
            labels=message.labels,
        )
        return message
    
    async def post_execute(
        self,
        message: TaskiqMessage,
        result: TaskiqResult[Any],
    ) -> None:
        """Log when job completes (success or failure)."""
        log_data = {
            "job_id": message.task_id,
            "task_name": message.task_name,
            "execution_time_seconds": result.execution_time,
            "is_error": result.is_err,
        }
        
        if result.is_err:
            log_data["error"] = str(result.error)[:500]
            logger.error("job_failed", **log_data)
        else:
            logger.info("job_completed", **log_data)
```

**Log output** (JSON via structlog):

```json
{"event": "job_started", "job_id": "abc123", "task_name": "check_expiring_tokens", "timestamp": "..."}
{"event": "job_completed", "job_id": "abc123", "execution_time_seconds": 2.34, "is_error": false}
```

### Health Checks

**Worker health** (for container orchestration):

```python
# Worker exposes health via Redis key
@broker.on_event(TaskiqEvents.WORKER_STARTUP)
async def startup(state: TaskiqState) -> None:
    state.worker_id = str(uuid.uuid4())
    # Start heartbeat task
    asyncio.create_task(heartbeat_loop(state))

async def heartbeat_loop(state: TaskiqState) -> None:
    """Update heartbeat key every 30 seconds."""
    while True:
        await state.redis.setex(
            f"dashtam:worker:{state.worker_id}:heartbeat",
            60,  # Expires in 60s if worker dies
            datetime.now(UTC).isoformat(),
        )
        await asyncio.sleep(30)
```

**API health endpoint**:

```python
@router.get("/health/jobs")
async def jobs_health(redis: Redis = Depends(get_redis)) -> dict:
    """Check job system health."""
    # Check broker connectivity
    try:
        await redis.ping()
        broker_healthy = True
    except Exception:
        broker_healthy = False
    
    # Check for active workers (heartbeat keys)
    worker_keys = await redis.keys("dashtam:worker:*:heartbeat")
    active_workers = len(worker_keys)
    
    # Check queue depth
    queue_depth = await redis.llen("dashtam:jobs")
    
    return {
        "status": "healthy" if broker_healthy and active_workers > 0 else "degraded",
        "broker_connected": broker_healthy,
        "active_workers": active_workers,
        "queue_depth": queue_depth,
    }
```

### Summary: Monitoring Approach

| Need | Solution | Location |
| ------ | ---------- | ---------- |
| Job health checks | API endpoint `/health/jobs` | dashtam-api |
| Queue status | API endpoint `/jobs/queued` | dashtam-api |
| Job results | API endpoint `/jobs/{id}/status` | dashtam-api |
| Real-time TUI display | Direct Redis queries | dashtam-terminal |
| Execution logs | Structured JSON logging | dashtam-jobs (stdout) |
| Debugging UI | TaskIQ Dashboard (optional) | Separate container |

---

## Initial Job Implementations

### Token Expiry Check

**Purpose**: Periodically check for expiring provider tokens and emit SSE events.

```python
# src/dashtam_jobs/tasks/tokens.py

@broker.task(
    schedule=[{"cron": "*/15 * * * *", "schedule_id": "token_expiry_check"}],
)
async def check_expiring_tokens(
    context: Annotated[Context, TaskiqDepends()],
) -> dict[str, int]:
    """Check for provider tokens expiring within threshold.
    
    Runs every 15 minutes. Emits ProviderTokenExpiringSoon domain event
    for each expiring token, which triggers SSE notification.
    
    Returns:
        Dict with counts: checked, expiring, notified
    """
    async with AsyncSession(context.state.db_engine) as session:
        repo = ProviderConnectionRepository(session)
        expiring = await repo.find_expiring_soon(threshold_hours=24)
        
        event_bus = context.state.event_bus
        for connection in expiring:
            event = ProviderTokenExpiringSoon(
                connection_id=connection.id,
                user_id=connection.user_id,
                provider_slug=connection.provider_slug,
                expires_at=connection.token_expires_at,
            )
            await event_bus.publish(event)
        
        return {
            "checked": await repo.count_active(),
            "expiring": len(expiring),
            "notified": len(expiring),
        }
```

---

## Docker Configuration

### Dockerfile (Multi-Stage)

**Location**: `docker/Dockerfile`

```dockerfile
# Base Stage - Common setup
FROM ghcr.io/astral-sh/uv:0.9.21-python3.14-trixie AS base
WORKDIR /app
RUN groupadd -r appuser -g 1000 && useradd -r -u 1000 -g appuser -m appuser
USER appuser

# Development Stage - Hot reload, full tooling
FROM base AS development
COPY --chown=appuser:appuser pyproject.toml README.md uv.loc[k] ./
COPY --chown=appuser:appuser src/ ./src/
RUN uv sync --all-groups
COPY --chown=appuser:appuser . .
CMD ["sh", "-c", "uv run taskiq worker dashtam_jobs.broker:broker --ack-type when_executed"]

# Builder Stage - Production dependency installation
FROM base AS builder
COPY --chown=appuser:appuser pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# Production Stage - Minimal runtime
FROM python:3.14-slim AS production
COPY --from=builder /app/.venv /app/.venv
COPY --chown=appuser:appuser . .
HEALTHCHECK --interval=30s --timeout=3s CMD pgrep -f "taskiq worker" || exit 1
CMD ["uv", "run", "taskiq", "worker", "dashtam_jobs.broker:broker", "--ack-type", "when_executed"]
```

### Docker Compose (Per Environment)

**Location**: `compose/docker-compose.dev.yml`

```yaml
name: dashtam-jobs-dev

services:
  worker:
    build:
      context: ..
      dockerfile: docker/Dockerfile
      target: development
    env_file:
      - ../env/.env.dev
    volumes:
      - ..:/app:rw
      - /app/.venv  # Exclude venv from mount
    depends_on:
      redis:
        condition: service_healthy
    networks:
      - dashtam-jobs-dev-network
      - dashtam-shared-network

  scheduler:
    build:
      context: ..
      dockerfile: docker/Dockerfile
      target: development
    command: ["sh", "-c", "uv run taskiq scheduler dashtam_jobs.scheduler:scheduler"]
    env_file:
      - ../env/.env.dev
    depends_on:
      worker:
        condition: service_started

  redis:
    image: redis:8.4-alpine
    ports:
      - "${JOBS_REDIS_PORT:-6381}:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]

networks:
  dashtam-jobs-dev-network:
    driver: bridge
  dashtam-shared-network:
    external: true
```

---

## Environment Configuration

### Required Variables

```bash
# env/.env.example

# Redis connection (required)
REDIS_URL=redis://redis:6379/0

# Database connection (for jobs that need DB access)
DATABASE_URL=postgresql+asyncpg://user:pass@postgres:5432/dashtam

# Optional: result backend TTL (default 86400 = 24 hours)
JOB_RESULT_TTL=86400

# Optional: log level
LOG_LEVEL=INFO
```

---

## Related Documentation

**In dashtam-api**:

- `docs/architecture/dependency-injection.md` — Section 10 covers jobs integration
- `src/infrastructure/jobs/monitor.py` — JobsMonitor implementation
- `src/presentation/routers/system.py` — `/health/jobs` endpoint
- `src/presentation/routers/api/v1/admin/jobs.py` — Admin jobs endpoint

**In dashtam-jobs**:

- `docs/adding-jobs.md` — Developer guide for adding new jobs

---

## Appendix: CLI Reference

### Worker Commands

```bash
# Start worker
taskiq worker dashtam_jobs.broker:broker

# With options
taskiq worker dashtam_jobs.broker:broker \
  --ack-type when_executed \
  --max-async-tasks 10 \
  --log-level INFO

# Graceful reload (SIGHUP)
kill -HUP <worker_pid>
```

### Scheduler Commands

```bash
# Start scheduler
taskiq scheduler dashtam_jobs.scheduler:scheduler
```

### Common Options

| Option | Description |
| -------- | ------------- |
| `--ack-type` | Acknowledgement mode: `when_received`, `when_executed`, `when_saved` |
| `--max-async-tasks` | Max concurrent async tasks |
| `--log-level` | Logging verbosity |
| `--use-process-pool` | Use ProcessPoolExecutor for CPU-bound tasks |
| `--max-process-pool-processes` | Number of processes in pool |

---

**Created**: 2026-01-19 | **Last Updated**: 2026-01-20
