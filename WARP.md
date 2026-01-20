# dashtam-jobs Project Rules

## Overview

This document contains project-specific rules and guidelines for the dashtam-jobs centralized background jobs service.

## Architecture

- **Centralized Service**: All Dashtam background jobs are defined in this single repository
- **TaskIQ Framework**: Uses TaskIQ for async-native task queuing with Redis backend
- **Simplified Layers**: Tasks → Infrastructure → Core (not full Hexagonal)
- **Jobs Orchestrate, Don't Implement**: Complex business logic lives in dashtam-api; jobs call it

## Code Patterns

### Task Definition

```python
@broker.task(
    retry_on_error=True,
    max_retries=3,
    timeout=300,
    labels={"category": "provider", "schedule": "*/15 * * * *"},
)
async def my_task(
    context: Annotated[Context, TaskiqDepends()],
) -> dict[str, int]:
    """Docstring with purpose, schedule info, and return type."""
    ...
```

### Settings

- All configuration via environment variables (Pydantic Settings)
- No hardcoded values for environment-specific settings
- Settings singleton: `from dashtam_jobs.core.settings import settings`

### Logging

- Use structlog for structured JSON logging
- Get logger: `from dashtam_jobs.core.logging import get_logger`
- Include `event` field for log aggregation filtering

## Development

### Container-Based Development

All development happens inside Docker containers:

```bash
make dev-up      # Start development environment
make dev-shell   # Shell into worker container
make dev-logs    # View logs
```

### Adding Dependencies

Inside the container:

```bash
uv add <package>                    # Production dependency
uv add --group dev <package>        # Dev dependency
uv add --group docs <package>       # Docs dependency
```

### Testing

```bash
make test           # All tests with coverage
make test-unit      # Unit tests only
make test-integration  # Integration tests only
```

### Verification (Pre-Commit)

```bash
make verify   # Format, lint, type-check, test, docs build
```

## Dependencies

### Production

- taskiq, taskiq-redis: Task queue framework
- pydantic-settings: Configuration management
- sqlalchemy[asyncio], asyncpg: Database access
- structlog: Structured logging
- redis: Redis client for direct access

### Development

- pytest, pytest-anyio, pytest-cov: Testing
- ruff: Linting and formatting
- mypy: Type checking

### Documentation

- mkdocs, mkdocs-material: Documentation site
- mkdocstrings[python]: API reference generation

## Conventions

### File Organization

```text
src/dashtam_jobs/
├── broker.py          # Broker configuration
├── scheduler.py       # Scheduler configuration
├── core/              # Settings, logging, utilities
├── tasks/             # Task definitions by domain
├── infrastructure/    # Database, repositories
└── middlewares/       # TaskIQ middlewares
```

### Naming

- Tasks: `verb_noun` (e.g., `check_expiring_tokens`, `sync_accounts`)
- Task files: Domain-based (e.g., `tokens.py`, `sync.py`)

### Return Values

- Tasks return `dict[str, Any]` with summary information
- Include counts: `{"checked": N, "processed": M, "errors": K}`

## Related Documentation

- Architecture: `docs/architecture/background-jobs.md`
- API Integration: See dashtam-api documentation
