COMPOSE := docker compose -f infra/docker-compose.yml --env-file .env

.PHONY: demo seed seed-memory data-deps down logs ps build test

demo: .env
	$(COMPOSE) up -d --build
	@echo ""
	@echo "Waiting for services to become healthy..."
	@sleep 5
	$(COMPOSE) ps
	@echo ""
	@echo "Backend  : http://localhost:8000/health"
	@echo "Frontend : http://localhost:3000"
	@command -v open >/dev/null && open http://localhost:3000 || true

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

.env:
	@echo "ERROR: .env is missing. Copy .env.example to .env and set REDIS_URL." >&2
	@exit 1
