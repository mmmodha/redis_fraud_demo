COMPOSE := docker compose -f infra/docker-compose.yml --env-file .env

.PHONY: demo seed seed-memory data-deps down logs ps build test rdi-status context-up ui ui-test ui-test-headed policy-index backend-deps

demo: .env
	$(COMPOSE) up -d --build
	@echo ""
	@echo "Waiting for backend to become healthy (max 90 s)..."
	@for i in $$(seq 1 30); do \
	  if curl -fsS http://localhost:8000/health >/dev/null 2>&1; then \
	    echo "  backend healthy"; break; \
	  fi; \
	  sleep 3; \
	done
	@echo "Waiting for frontend to become reachable (max 30 s)..."
	@for i in $$(seq 1 10); do \
	  if curl -fsS http://localhost:3000/ >/dev/null 2>&1; then \
	    echo "  frontend reachable"; break; \
	  fi; \
	  sleep 3; \
	done
	@$(COMPOSE) ps
	@echo ""
	@echo "Backend  : http://localhost:8000/health"
	@echo "Frontend : http://localhost:3000"
	@if command -v open >/dev/null 2>&1; then open http://localhost:3000; \
	 elif command -v xdg-open >/dev/null 2>&1; then xdg-open http://localhost:3000; \
	 fi

data-deps:
	pip install -r data/requirements.txt

seed: data-deps
	python -m data.seed

seed-memory: data-deps
	python -m data.seed_memory

down:
	$(COMPOSE) down -v

logs:
	$(COMPOSE) logs -f

ps:
	$(COMPOSE) ps

build:
	$(COMPOSE) build

# Show the current RDI sync lag (Postgres → Redis) from the backend endpoint.
# The same JSON powers the RDI side panel in the UI.
rdi-status:
	@curl -fsS http://localhost:8000/rdi/status || \
	  (echo "backend not reachable on :8000" >&2; exit 1)
	@echo

test:
	pip install -r backend/requirements-dev.txt
	pytest tests/ -v

# Provision the Redis Context Retriever surface + agent key. Runs inside a
# one-shot Docker container so the presenter doesn't need Python 3.11+ on
# the host. Idempotent: a second run reuses the existing surface and mints
# a fresh agent key. See docs/context-retriever-setup.md.
context-up: .env
	@bash scripts/context-up.sh

# Install backend deps locally (used by policy-index when not running in Docker).
backend-deps:
	pip install -r backend/requirements.txt

# Drop and rebuild the RediSearch policy index `idx:policies` from
# data/policies/*.md. Idempotent — safe to re-run after a corpus update.
# Sources .env (for REDIS_URL) inside the shell so the value never appears in
# command-line arguments.
policy-index: .env
	@set -a; . ./.env; set +a; \
	  python scripts/build_policy_index.py

# Run the Next.js frontend dev server. Defaults to port 3030 to avoid
# conflicting with the Docker frontend container (port :3000). The
# docker-compose `frontend` service is the production target; use this
# for hot-reload iteration. Set FRONTEND_PORT=3000 to override after
# stopping the docker container (see docs/README.md).
ui:
	cd frontend && npm install --no-audit --no-fund --silent
	cd frontend && PORT=$${FRONTEND_PORT:-3030} \
		NEXT_PUBLIC_BACKEND_URL=$${NEXT_PUBLIC_BACKEND_URL:-http://localhost:8000} \
		npm run dev -- -p $${FRONTEND_PORT:-3030}

# Playwright smoke tests. Headless by default (CI mode); use ui-test-headed
# during development to watch the browser.
ui-test:
	cd frontend && npx playwright install --with-deps chromium >/dev/null 2>&1 || true
	cd frontend && npx playwright test

ui-test-headed:
	cd frontend && npx playwright install --with-deps chromium >/dev/null 2>&1 || true
	cd frontend && npx playwright test --headed

.env:
	@echo "ERROR: .env is missing. Copy .env.example to .env and set REDIS_URL." >&2
	@exit 1
