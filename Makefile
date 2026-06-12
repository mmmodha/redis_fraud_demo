COMPOSE := docker compose -f infra/docker-compose.yml --env-file .env

.PHONY: demo demo-reset demo-verify seed seed-memory down logs ps build \
        test rdi-status context-up ui ui-test ui-test-headed policy-index

# ---- One-shot demo lifecycle ---------------------------------------------
# `make demo`        — build, start, seed, verify, print URLs (idempotent).
# `make demo-reset`  — full teardown (containers + named volumes).
# `make demo-verify` — 4-hero curl regression + Playwright (in container).

demo: .env
	@bash scripts/demo.sh

demo-reset: .env
	@bash scripts/demo-reset.sh

demo-verify: .env
	@bash scripts/demo-verify.sh

# ---- Individual operations (mostly delegated to scripts) -----------------

seed: .env
	@bash scripts/seed.sh

# Run only the Agent Memory / disputes / pending-review pass.
seed-memory: .env
	@bash -c '. scripts/_lib.sh; configure_redis_mode; _append_profile seed; \
	  compose run --rm seeder python -m data.seed_memory'

# Rebuild only the RediSearch policy index (subset of `make seed`).
policy-index: .env
	@bash scripts/policy-index.sh

down:
	$(COMPOSE) down -v

logs:
	$(COMPOSE) logs -f

ps:
	$(COMPOSE) ps

build:
	$(COMPOSE) build

# Show the current RDI sync lag (Postgres → Redis) from the backend.
rdi-status:
	@curl -fsS http://localhost:8000/rdi/status || \
	  (echo "backend not reachable on :8000" >&2; exit 1)
	@echo

# In-container test runner — uses the live backend image so deps match
# what the running stack ships with.
test:
	$(COMPOSE) run --rm --no-deps backend \
	  sh -c 'pip install --quiet pytest pytest-asyncio && pytest /app/tests -v'

# Provision the Redis Context Retriever surface + agent key. Idempotent.
context-up: .env
	@bash scripts/context-up.sh

# Run the Next.js frontend dev server on the host (hot-reload iteration).
# Not part of the bootstrap path; reserved for UI development.
ui:
	cd frontend && npm install --no-audit --no-fund --silent
	cd frontend && PORT=$${FRONTEND_PORT:-3030} \
	    NEXT_PUBLIC_BACKEND_URL=$${NEXT_PUBLIC_BACKEND_URL:-http://localhost:8000} \
	    npm run dev -- -p $${FRONTEND_PORT:-3030}

# Playwright on the host (headed development). `make demo-verify` is the
# headless, in-container equivalent used in the bootstrap path.
ui-test:
	cd frontend && npx playwright install --with-deps chromium >/dev/null 2>&1 || true
	cd frontend && npx playwright test

ui-test-headed:
	cd frontend && npx playwright install --with-deps chromium >/dev/null 2>&1 || true
	cd frontend && npx playwright test --headed

.env:
	@echo "ERROR: .env is missing. Copy .env.example to .env." >&2
	@echo "       (Leave REDIS_URL blank to use the bundled redis-stack.)" >&2
	@exit 1
