# Changelog

All notable changes to dashtam-jobs will be documented in this file.

## [0.2.1] - 2026-01-23

### Features

- feat: Background Job Foundation (#1)

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.0] - 2026-01-20

### Added

- **SSE Publisher for Cross-Service Event Notifications**
  - `SSEPublisher` class (`src/dashtam_jobs/infrastructure/sse_publisher.py`)
    - `publish_to_user()`: Send events to specific user's SSE channel
    - `broadcast()`: Send events to all connected clients
    - Uses same Redis pub/sub channels as API's SSE subscriber
  - UUID v7 generation for event IDs (matching API pattern)
  - Worker startup initialization via broker lifecycle hooks
  - 10 unit tests for SSE publisher

- **Token Expiry SSE Notifications**
  - `check_expiring_tokens` task now publishes `provider.token.expiring` events
  - Real-time notification to users when their provider credentials are expiring

- **Documentation**
  - `docs/guides/cross-service-sse-publishing.md`: Guide for publishing SSE events from jobs
  - MkDocs awesome-pages navigation configuration

### Changed

- **Test Fixtures**: Added `mock_sse_publisher` fixture for testing tasks that publish events

### Dependencies

- Added `uuid7>=0.1.0` for UUID v7 generation

### Technical Notes

- **Zero Breaking Changes**: All 26 tests pass, 62% coverage
- **New Test File**: `tests/unit/test_sse_publisher.py`
- Files changed: 13 files

## [0.1.0] - 2026-01-19

### Added

- **Initial Release** - Centralized background jobs service for Dashtam

- **Core Infrastructure**
  - TaskIQ broker with Redis backend (`src/dashtam_jobs/broker.py`)
  - TaskIQ scheduler for cron-based scheduling (`src/dashtam_jobs/scheduler.py`)
  - Pydantic Settings configuration (`src/dashtam_jobs/core/settings.py`)
  - Structured JSON logging with structlog (`src/dashtam_jobs/core/logging.py`)

- **Database Layer**
  - Async SQLAlchemy database manager (`src/dashtam_jobs/infrastructure/database.py`)
  - ProviderConnection repository for token queries (`src/dashtam_jobs/infrastructure/repositories/`)

- **Tasks**
  - `check_expiring_tokens`: Monitors provider token expiration (15-minute schedule)
    - Configurable threshold via `TOKEN_EXPIRY_THRESHOLD_HOURS`
    - Creates `ProviderTokenExpiringSoon` domain events

- **Domain Events**
  - `ProviderTokenExpiringSoon` event for token expiry notifications

- **Middleware**
  - Logging middleware for task execution tracing

- **Documentation**
  - MkDocs Material documentation site
  - Architecture documentation (`docs/architecture/background-jobs.md`)
  - API reference with mkdocstrings

- **Development Infrastructure**
  - Docker Compose development environment
  - Docker Compose test environment
  - Makefile with 30+ targets for development workflow
  - GitHub Actions CI/CD pipeline
  - Branch protection for main and development

### Technical Notes

- **Test Coverage**: 17 tests, 57% coverage
- **Python**: 3.14+
- **Key Dependencies**: taskiq, taskiq-redis, pydantic-settings, sqlalchemy[asyncio], structlog
- Files: 45 files, 5369 insertions
