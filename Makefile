.PHONY: help setup dev-up dev-down dev-logs dev-shell dev-worker-shell dev-scheduler-shell dev-redis-cli dev-restart dev-status dev-build dev-rebuild test-up test-down test test-unit test-integration ci-test ci-lint lint format type-check verify lint-md lint-md-check docs-serve docs-build docs-stop clean status-all ps check

# ==============================================================================
# HELP
# ==============================================================================

.DEFAULT_GOAL := help

help:
	@echo "🎯 Dashtam Jobs - Centralized Background Jobs Service"
	@echo ""
	@echo "📋 Quick Start:"
	@echo "  1. Create shared network:  docker network create dashtam-shared-network"
	@echo "  2. Start dev:              make dev-up"
	@echo "  3. View logs:              make dev-logs"
	@echo ""
	@echo "🚀 Development:"
	@echo "  make dev-up          - Start development environment"
	@echo "  make dev-down        - Stop development environment"
	@echo "  make dev-logs        - View development logs (follow)"
	@echo "  make dev-shell       - Shell into worker container"
	@echo "  make dev-redis-cli   - Redis CLI"
	@echo "  make dev-restart     - Restart development environment"
	@echo "  make dev-build       - Build development containers"
	@echo "  make dev-rebuild     - Rebuild containers (no cache)"
	@echo "  make dev-status      - Show service status"
	@echo ""
	@echo "🧪 Testing:"
	@echo "  make test-up         - Start test environment"
	@echo "  make test-down       - Stop test environment"
	@echo "  make test            - Run all tests with coverage"
	@echo "  make test-unit       - Unit tests only"
	@echo "  make test-integration - Integration tests only"
	@echo ""
	@echo "🤖 CI/CD:"
	@echo "  make ci-test         - Tests only (matches GitHub Actions)"
	@echo "  make ci-lint         - Linting only (matches GitHub Actions)"
	@echo ""
	@echo "✨ Code Quality:"
	@echo "  make lint            - Run Python linters (ruff)"
	@echo "  make format          - Format Python code (ruff)"
	@echo "  make type-check      - Type check with mypy"
	@echo "  make verify          - 🔥 FULL verification (pre-release)"
	@echo "  make lint-md         - Lint markdown files"
	@echo ""
	@echo "📚 Documentation:"
	@echo "  make docs-serve      - Start MkDocs live preview"
	@echo "  make docs-build      - Build static docs (strict mode)"
	@echo "  make docs-stop       - Stop MkDocs server"
	@echo ""
	@echo "🔧 Setup & Utilities:"
	@echo "  make setup           - First-time setup (idempotent)"
	@echo "  make check           - Verify prerequisites"
	@echo "  make status-all      - Show all environment status"
	@echo "  make ps              - Show all dashtam-jobs containers"
	@echo "  make clean           - Stop and clean ALL environments"
	@echo ""
	@echo "📚 Full docs: https://faiyaz7283.github.io/dashtam-jobs/"

# ==============================================================================
# SETUP
# ==============================================================================

setup:
	@echo "🚀 Dashtam Jobs First-Time Setup"
	@echo ""
	@echo "📝 Step 1: Creating env/.env.dev from template..."
	@if [ -f env/.env.dev ]; then \
		echo "  ℹ️  env/.env.dev already exists - skipping"; \
	else \
		cp env/.env.dev.example env/.env.dev; \
		echo "  ✅ Created env/.env.dev"; \
	fi
	@echo ""
	@echo "🔗 Step 2: Checking shared network..."
	@docker network inspect dashtam-shared-network >/dev/null 2>&1 || \
		(docker network create dashtam-shared-network && echo "  ✅ Created dashtam-shared-network")
	@echo ""
	@echo "✅ Setup complete!"
	@echo ""
	@echo "📝 Next steps:"
	@echo "  1. Update env/.env.dev with your database credentials"
	@echo "  2. Start development environment: make dev-up"

# ==============================================================================
# DEVELOPMENT ENVIRONMENT
# ==============================================================================

dev-up: _ensure-env-dev _ensure-network
	@echo "🚀 Starting DEVELOPMENT environment..."
	@docker compose -f compose/docker-compose.dev.yml up -d --remove-orphans
	@echo ""
	@echo "📦 Syncing dependencies..."
	@docker compose -f compose/docker-compose.dev.yml exec -T worker uv sync --all-groups > /dev/null 2>&1 || docker compose -f compose/docker-compose.dev.yml exec worker uv sync --all-groups
	@echo ""
	@echo "✅ Development services started!"
	@echo ""
	@echo "🔴 Redis:     localhost:6381"
	@echo ""
	@echo "📋 Commands:"
	@echo "   Logs:  make dev-logs"
	@echo "   Shell: make dev-shell"

dev-down:
	@echo "🛑 Stopping DEVELOPMENT environment..."
	@docker compose -f compose/docker-compose.dev.yml down
	@echo "✅ Development stopped"

dev-logs:
	@docker compose -f compose/docker-compose.dev.yml logs -f

dev-shell:
	@docker compose -f compose/docker-compose.dev.yml exec worker /bin/bash

dev-worker-shell:
	@docker compose -f compose/docker-compose.dev.yml exec worker /bin/bash

dev-scheduler-shell:
	@docker compose -f compose/docker-compose.dev.yml exec scheduler /bin/bash

dev-redis-cli:
	@docker compose -f compose/docker-compose.dev.yml exec redis redis-cli

dev-restart: dev-down dev-up

dev-status:
	@echo "📊 Development Status:"
	@docker compose -f compose/docker-compose.dev.yml ps

dev-build: _ensure-env-dev _ensure-network
	@echo "🔨 Building DEVELOPMENT containers..."
	@docker compose -f compose/docker-compose.dev.yml build
	@echo "✅ Development containers built"

dev-rebuild: _ensure-env-dev _ensure-network
	@echo "🔨 Rebuilding DEVELOPMENT containers (no cache)..."
	@docker compose -f compose/docker-compose.dev.yml build --no-cache
	@echo "📦 Restarting with fresh dependencies..."
	@docker compose -f compose/docker-compose.dev.yml down
	@docker compose -f compose/docker-compose.dev.yml up -d --remove-orphans
	@echo "📦 Syncing dependencies..."
	@docker compose -f compose/docker-compose.dev.yml exec -T worker uv sync --all-groups > /dev/null 2>&1 || docker compose -f compose/docker-compose.dev.yml exec worker uv sync --all-groups
	@echo "✅ Development containers rebuilt"

# ==============================================================================
# TEST ENVIRONMENT
# ==============================================================================

test-up: _ensure-env-test _ensure-network
	@echo "🧪 Starting TEST environment..."
	@docker compose -f compose/docker-compose.test.yml up -d --remove-orphans
	@sleep 3
	@echo ""
	@echo "✅ Test services started!"
	@echo ""
	@echo "🧪 Run tests: make test"

test-down:
	@echo "🛑 Stopping TEST environment..."
	@docker compose -f compose/docker-compose.test.yml down
	@echo "✅ Test stopped"

# ==============================================================================
# TESTING
# ==============================================================================

TEST_PATH_ALL ?= tests/
TEST_PATH_UNIT ?= tests/unit/
TEST_PATH_INTEGRATION ?= tests/integration/

test:
	@echo "🧪 Running tests with coverage..."
	@[ "$$(docker compose -f compose/docker-compose.test.yml ps --status running -q worker)" ] || make test-up
	@docker compose -f compose/docker-compose.test.yml exec -T worker uv run pytest $(if $(TEST_PATH),$(TEST_PATH),$(TEST_PATH_ALL)) -v --cov=src --cov-report=term-missing --cov-report=html $(ARGS)

test-unit:
	@echo "🧪 Running unit tests..."
	@[ "$$(docker compose -f compose/docker-compose.test.yml ps --status running -q worker)" ] || make test-up
	@docker compose -f compose/docker-compose.test.yml exec -T worker uv run pytest $(if $(TEST_PATH),$(TEST_PATH),$(TEST_PATH_UNIT)) -v $(ARGS)

test-integration:
	@echo "🧪 Running integration tests..."
	@[ "$$(docker compose -f compose/docker-compose.test.yml ps --status running -q worker)" ] || make test-up
	@docker compose -f compose/docker-compose.test.yml exec -T worker uv run pytest $(if $(TEST_PATH),$(TEST_PATH),$(TEST_PATH_INTEGRATION)) -v $(ARGS)

# ==============================================================================
# CI/CD
# ==============================================================================

ci-test: _ensure-env-ci
	@echo "🤖 Running CI tests..."
	@docker compose -f compose/docker-compose.ci.yml up -d --build --remove-orphans
	@sleep 3
	@docker compose -f compose/docker-compose.ci.yml exec -T worker \
		uv run pytest tests/ -v \
		--cov=src \
		--cov-report=term-missing \
		--cov-report=html || (docker compose -f compose/docker-compose.ci.yml down -v && exit 1)
	@docker compose -f compose/docker-compose.ci.yml down -v
	@echo "✅ CI tests passed!"

ci-lint: _ensure-env-ci
	@echo "🔍 Running CI linting..."
	@docker compose -f compose/docker-compose.ci.yml up -d --build --remove-orphans
	@sleep 3
	@docker compose -f compose/docker-compose.ci.yml exec -T worker uv run ruff check src/ tests/ || (docker compose -f compose/docker-compose.ci.yml down -v && exit 1)
	@docker compose -f compose/docker-compose.ci.yml exec -T worker uv run ruff format --check src/ tests/ || (docker compose -f compose/docker-compose.ci.yml down -v && exit 1)
	@docker run --rm -v $(PWD):/workspace:ro -w /workspace node:24-alpine sh -c "npx markdownlint-cli2 '**/*.md' || exit 1" || (docker compose -f compose/docker-compose.ci.yml down -v && exit 1)
	@docker compose -f compose/docker-compose.ci.yml down -v
	@echo "✅ CI linting passed!"

# ==============================================================================
# CODE QUALITY
# ==============================================================================

lint: dev-up
	@echo "🔍 Running linters..."
	@docker compose -f compose/docker-compose.dev.yml exec worker uv run ruff check src/ tests/

format: dev-up
	@echo "✨ Formatting code..."
	@docker compose -f compose/docker-compose.dev.yml exec worker uv run ruff format src/ tests/
	@docker compose -f compose/docker-compose.dev.yml exec worker uv run ruff check --fix src/ tests/

type-check: dev-up
	@echo "🔍 Running type checks with mypy..."
	@docker compose -f compose/docker-compose.dev.yml exec -w /app worker uv run mypy src tests

# ==============================================================================
# COMPREHENSIVE VERIFICATION
# ==============================================================================

verify: test-up
	@echo "🔍 ====================================="
	@echo "🔍 COMPREHENSIVE VERIFICATION (fail-fast)"
	@echo "🔍 ====================================="
	@echo ""
	@echo "📋 Running 6 verification steps:"
	@echo "   1. Format (auto-fix)"
	@echo "   2. Lint"
	@echo "   3. Type check"
	@echo "   4. Tests"
	@echo "   5. Markdown linting"
	@echo "   6. Documentation build"
	@echo ""
	@echo "✨ Step 1/6: Formatting (auto-fix)..."; \
	docker compose -f compose/docker-compose.test.yml exec -T worker uv run ruff format src/ tests/ || { echo "❌ Format command failed"; exit 1; }; \
	docker compose -f compose/docker-compose.test.yml exec -T worker uv run ruff check --fix src/ tests/ || { echo "❌ Format check --fix failed"; exit 1; }; \
	echo "✅ Formatting completed"; \
	echo ""; \
	echo "🔍 Step 2/6: Linting..."; \
	docker compose -f compose/docker-compose.test.yml exec -T worker uv run ruff check src/ tests/ || { echo "❌ Lint failed"; exit 1; }; \
	echo "✅ Lint passed"; \
	echo ""; \
	echo "🔍 Step 3/6: Type checking..."; \
	docker compose -f compose/docker-compose.test.yml exec -T -w /app worker uv run mypy src tests || { echo "❌ Type check failed"; exit 1; }; \
	echo "✅ Type check passed"; \
	echo ""; \
	echo "🧪 Step 4/6: Running all tests with coverage..."; \
	docker compose -f compose/docker-compose.test.yml exec -T worker uv run pytest tests/ -v --cov=src --cov-report=term-missing --cov-report=html || { echo "❌ Tests failed"; exit 1; }; \
	echo "✅ Tests passed"; \
	echo ""; \
	echo "📝 Step 5/6: Linting markdown files..."; \
	docker run --rm -v $(PWD):/workspace:ro -w /workspace node:24-alpine sh -c "npx markdownlint-cli2 '**/*.md' || exit 1" || { echo "❌ Markdown linting failed"; exit 1; }; \
	echo "✅ Markdown linting passed"; \
	echo ""; \
	echo "📚 Step 6/6: Building documentation (strict mode)..."; \
	docker compose -f compose/docker-compose.test.yml exec -T worker uv sync --all-groups > /dev/null 2>&1; \
	docker compose -f compose/docker-compose.test.yml exec -T worker uv run mkdocs build --strict 2>&1 | tee /tmp/mkdocs-build.log || true; \
	if grep -E "WARNING" /tmp/mkdocs-build.log | grep -v "griffe:" | grep -v "mkdocs_autorefs:" | grep -q .; then \
		echo "❌ Documentation warnings found"; \
		exit 1; \
	fi; \
	echo "✅ Documentation built successfully"; \
	echo ""; \
	echo "🎉 ====================================="; \
	echo "🎉 ALL VERIFICATION CHECKS PASSED!"; \
	echo "🎉 ====================================="

# ==============================================================================
# MARKDOWN LINTING
# ==============================================================================

MARKDOWN_LINT_IMAGE := node:24-alpine
MARKDOWN_LINT_CMD := npx markdownlint-cli2
MARKDOWN_BASE_PATTERN := '**/*.md'

lint-md:
	@echo "🔍 Linting markdown files..."
	@docker run --rm \
		-v $(PWD):/workspace:ro \
		-w /workspace \
		$(MARKDOWN_LINT_IMAGE) \
		sh -c "$(MARKDOWN_LINT_CMD) $(MARKDOWN_BASE_PATTERN) || exit 1"
	@echo "✅ Markdown linting complete!"

lint-md-check: lint-md

# ==============================================================================
# DOCUMENTATION
# ==============================================================================

docs-serve:
	@echo "📚 Starting MkDocs live preview..."
	@docker compose -f compose/docker-compose.dev.yml ps -q worker > /dev/null 2>&1 || make dev-up
	@echo "📦 Ensuring MkDocs dependencies..."
	@docker compose -f compose/docker-compose.dev.yml exec -T worker uv sync --all-groups > /dev/null 2>&1 || docker compose -f compose/docker-compose.dev.yml exec worker uv sync --all-groups
	@docker compose -f compose/docker-compose.dev.yml exec -d worker sh -c "cd /app && PYTHONUNBUFFERED=1 uv run mkdocs serve --dev-addr=0.0.0.0:8001"
	@sleep 2
	@echo ""
	@echo "✅ MkDocs server started!"
	@echo "📖 Docs: http://localhost:8001"
	@echo "🛑 Stop: make docs-stop"

docs-build:
	@echo "🏭️  Building documentation..."
	@docker compose -f compose/docker-compose.dev.yml ps -q worker > /dev/null 2>&1 || make dev-up
	@echo "📦 Ensuring MkDocs dependencies..."
	@docker compose -f compose/docker-compose.dev.yml exec -T worker uv sync --all-groups > /dev/null 2>&1 || docker compose -f compose/docker-compose.dev.yml exec worker uv sync --all-groups
	@docker compose -f compose/docker-compose.dev.yml exec worker uv run mkdocs build
	@echo "✅ Documentation built successfully to site/"

docs-stop:
	@echo "🛑 Stopping MkDocs server..."
	@docker compose -f compose/docker-compose.dev.yml restart worker
	@echo "✅ MkDocs stopped"

# ==============================================================================
# UTILITIES
# ==============================================================================

check:
	@echo "🔍 Checking setup..."
	@echo ""
	@echo "Docker:"
	@docker --version
	@docker compose version
	@echo ""
	@echo "Shared Network:"
	@docker network inspect dashtam-shared-network >/dev/null 2>&1 && echo "✅ dashtam-shared-network exists" || echo "❌ dashtam-shared-network missing (run: docker network create dashtam-shared-network)"
	@echo ""
	@echo "✅ All checks passed!"

status-all:
	@echo "=============== Development ==============="
	@docker compose -f compose/docker-compose.dev.yml ps 2>/dev/null || echo "Not running"
	@echo ""
	@echo "================== Test ==================="
	@docker compose -f compose/docker-compose.test.yml ps 2>/dev/null || echo "Not running"

ps:
	@echo "📊 Dashtam Jobs Containers:"
	@docker ps -a --filter "name=dashtam-jobs" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

clean:
	@echo "⚠️  DESTRUCTIVE: This will DELETE all data!"
	@echo ""
	@read -p "Type 'DELETE ALL DATA' to confirm: " confirm; \
	if [ "$$confirm" != "DELETE ALL DATA" ]; then \
		echo "❌ Cancelled"; \
		exit 1; \
	fi
	@echo ""
	@echo "🧹 Cleaning all environments..."
	@docker compose -f compose/docker-compose.dev.yml down -v --remove-orphans 2>/dev/null || true
	@docker compose -f compose/docker-compose.test.yml down -v --remove-orphans 2>/dev/null || true
	@docker compose -f compose/docker-compose.ci.yml down -v --remove-orphans 2>/dev/null || true
	@echo "✅ Cleanup complete"

# ==============================================================================
# INTERNAL HELPERS
# ==============================================================================

_ensure-env-dev:
	@if [ ! -f env/.env.dev ]; then \
		echo "📋 Creating env/.env.dev from example..."; \
		cp env/.env.dev.example env/.env.dev; \
		echo "✅ Created env/.env.dev"; \
		echo "⚠️  Update with your secrets before first run!"; \
	fi

_ensure-env-test:
	@if [ ! -f env/.env.test ]; then \
		echo "📋 Creating env/.env.test from example..."; \
		cp env/.env.test.example env/.env.test; \
		echo "✅ Created env/.env.test"; \
	fi

_ensure-env-ci:
	@if [ ! -f env/.env.ci ]; then \
		echo "📋 Creating env/.env.ci from example..."; \
		cp env/.env.ci.example env/.env.ci; \
		echo "✅ Created env/.env.ci"; \
	fi

_ensure-network:
	@docker network inspect dashtam-shared-network >/dev/null 2>&1 || \
		(echo "📋 Creating dashtam-shared-network..." && docker network create dashtam-shared-network)
