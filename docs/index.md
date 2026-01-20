# Dashtam Jobs

Centralized background jobs service for Dashtam.

## Overview

**dashtam-jobs** provides a centralized, async-native task queue system for all Dashtam applications. It enables deferred execution, scheduled jobs, and long-running tasks without blocking API responses or TUI interactions.

## Key Features

- **Single source of truth** — All job definitions in one place
- **Zero drift** — API, Terminal, and future apps share identical job implementations
- **Async-native** — Built on Python's asyncio, matches Dashtam's async architecture
- **Type-safe** — Full PEP-612 type hints with autocomplete support
- **Fault-tolerant** — Acknowledgements, retries, and persistent Redis queues
- **Observable** — Job status tracking, execution times, error logging

## Quick Start

```bash
# Start development environment
make dev-up

# View logs
make dev-logs

# Run tests
make test
```

## Architecture

See [Background Jobs Architecture](architecture/background-jobs.md) for detailed documentation.
