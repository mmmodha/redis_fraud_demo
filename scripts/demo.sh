#!/usr/bin/env bash
# `make demo` orchestrator: build → up → seed → smoke-check → print URLs.
# Zero-config (no REDIS_URL / no ANTHROPIC_API_KEY) bundles redis-stack and
# the deterministic stub agent. Presenter mode (both set) is unchanged.
# Idempotent — rerunning leaves a healthy stack ready for a demo.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=./_lib.sh
. "${SCRIPT_DIR}/_lib.sh"

configure_redis_mode

echo "Redis mode : ${REDIS_MODE}  (bundled redis-stack | external REDIS_URL)"
# Resolved agent mode mirrors the backend's auto-detect: explicit AGENT_MODE
# wins; otherwise ANTHROPIC_API_KEY presence picks claude vs mock.
if [[ -n "${AGENT_MODE:-}" ]]; then
  AGENT_MODE_LABEL="${AGENT_MODE}"
elif [[ -n "${ANTHROPIC_API_KEY:-}" ]]; then
  AGENT_MODE_LABEL="claude"
else
  AGENT_MODE_LABEL="mock"
fi
echo "Agent mode : ${AGENT_MODE_LABEL}  (claude | stub | mock)"

echo "Building images..."
compose build

echo "Starting services..."
compose up -d --remove-orphans

echo "Waiting for backend health (max 90s)..."
wait_http "http://localhost:8000/health" 90
echo "  backend healthy"

echo "Waiting for frontend (max 30s)..."
wait_http "http://localhost:3000/" 30
echo "  frontend reachable"

echo "Seeding Postgres + Redis (idempotent)..."
"${SCRIPT_DIR}/seed.sh"

echo "Smoke-checking 4 heroes..."
verify_heroes_curl

compose ps

cat <<EOF

✓ demo ready
  Backend  : http://localhost:8000/health
  Frontend : http://localhost:3000
  Redis    : ${REDIS_MODE}
EOF

if command -v open >/dev/null 2>&1; then
  open http://localhost:3000 >/dev/null 2>&1 || true
elif command -v xdg-open >/dev/null 2>&1; then
  xdg-open http://localhost:3000 >/dev/null 2>&1 || true
fi
