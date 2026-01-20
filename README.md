# dashtam-jobs

> Centralized background jobs service for Dashtam

[![Documentation](https://img.shields.io/badge/docs-mkdocs-blue)](https://faiyaz7283.github.io/dashtam-jobs/)
[![Test Suite](https://github.com/faiyaz7283/dashtam-jobs/workflows/Test%20Suite/badge.svg)](https://github.com/faiyaz7283/dashtam-jobs/actions)
[![codecov](https://codecov.io/gh/faiyaz7283/dashtam-jobs/branch/development/graph/badge.svg)](https://codecov.io/gh/faiyaz7283/dashtam-jobs)
[![Python 3.14](https://img.shields.io/badge/python-3.14-blue.svg)](https://www.python.org/downloads/)
[![TaskIQ](https://img.shields.io/badge/TaskIQ-0.12+-green.svg)](https://taskiq-python.github.io/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Overview

Async-native task queue for Dashtam applications. Enables deferred execution, scheduled jobs, and long-running tasks without blocking API responses.

## Features

- **Single source of truth** — All job definitions in one place
- **Async-native** — Built on Python's asyncio with TaskIQ
- **Type-safe** — Full type hints with autocomplete support
- **Fault-tolerant** — Retries, persistent Redis queues
- **Observable** — Job status tracking, structured logging

## Quick Start

### Prerequisites

- **Docker** and Docker Compose v2.0+
- **Make** (for convenience commands)

### Setup

```bash
git clone git@github.com:faiyaz7283/dashtam-jobs.git
cd dashtam-jobs
make setup      # Creates env files
make dev-up     # Starts worker, scheduler, Redis
```

### Verify

```bash
make dev-logs   # View worker logs
make test       # Run tests
```

## Development

All development happens inside Docker containers:

```bash
make dev-up       # Start development environment
make dev-shell    # Shell into worker container
make dev-logs     # View logs
make dev-down     # Stop environment
make test         # Run tests with coverage
make verify       # Full CI suite (lint + types + tests)
```

### Adding Dependencies

```bash
make dev-shell
uv add <package>                # Production dependency
uv add --group dev <package>    # Dev dependency
```

## Adding New Jobs

**Step 1**: Create task file in `src/dashtam_jobs/tasks/`:

```python
from dashtam_jobs.broker import broker

@broker.task
async def my_job(param: str) -> dict:
    """Job description."""
    # Implementation
    return {"status": "completed"}
```

**Step 2**: Register in `src/dashtam_jobs/tasks/__init__.py`

**Step 3**: Add schedule (optional) in `src/dashtam_jobs/scheduler.py`:

```python
from dashtam_jobs.tasks.my_module import my_job

scheduler.register_cron(my_job, "0 * * * *")  # Every hour
```

**Step 4**: Add tests in `tests/unit/test_tasks_*.py`

## Architecture

```text
┌─────────────┐    enqueue     ┌─────────────┐
│  Dashtam    │ ─────────────► │    Redis    │
│    API      │                │   (queue)   │
└─────────────┘                └──────┬──────┘
                                      │
                                      ▼
                               ┌─────────────┐
                               │   Worker    │
                               │  (TaskIQ)   │
                               └──────┬──────┘
                                      │
                    ┌─────────────────┼─────────────────┐
                    ▼                 ▼                 ▼
             ┌───────────┐     ┌───────────┐     ┌───────────┐
             │ check_    │     │  sync_    │     │  future   │
             │ tokens    │     │  data     │     │  jobs...  │
             └───────────┘     └───────────┘     └───────────┘
```

## Technology Stack

| Component | Technology |
| ----------- | ------------ |
| Language | Python 3.14, UV |
| Task Queue | TaskIQ |
| Broker | Redis (ListQueueBroker) |
| Scheduler | TaskIQ Scheduler |
| Testing | pytest |

## License

[MIT License](LICENSE)

---

**Part of [Dashtam](https://github.com/faiyaz7283/Dashtam)**
