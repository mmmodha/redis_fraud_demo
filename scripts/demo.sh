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

# Auto-provision the managed Context Retriever surface when the colleague
# has supplied both an admin key and an external REDIS_URL. Bootstrap is
# idempotent (finds-or-creates by name), writes CTX_SURFACE_ID +
# CTX_AGENT_KEY back to .env BEFORE the backend container starts so the
# new values are visible at startup. Standalone `make context-up` is
# unaffected.
if [[ -n "${CTX_ADMIN_KEY:-}" ]]; then
  if [[ "${REDIS_MODE}" != "external" ]]; then
    echo "ERROR: CTX_ADMIN_KEY requires REDIS_URL (rediss://...). Either unset CTX_ADMIN_KEY for stub mode or set REDIS_URL." >&2
    exit 1
  fi
  echo "Context Retriever : provisioning surface (idempotent)..."
  "${SCRIPT_DIR}/context-up.sh"
  # Re-source so subsequent compose calls see the freshly minted
  # CTX_SURFACE_ID + CTX_AGENT_KEY the bootstrap wrote to .env.
  set -a; . "${ENV_FILE}"; set +a
fi

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
