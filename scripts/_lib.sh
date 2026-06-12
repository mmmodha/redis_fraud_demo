#!/usr/bin/env bash
# Shared helpers for demo.sh / demo-reset.sh / demo-verify.sh / seed.sh.
# Source this file — it is not meant to be executed directly.
#
# Secrets policy: this library never echoes REDIS_URL, ANTHROPIC_API_KEY,
# CTX_ADMIN_KEY, CTX_AGENT_KEY, or any other credential value.

REPO_ROOT="${REPO_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
ENV_FILE="${ENV_FILE:-${REPO_ROOT}/.env}"
COMPOSE_FILE="${COMPOSE_FILE:-${REPO_ROOT}/infra/docker-compose.yml}"
LOCAL_REDIS_URL="redis://redis-stack:6379"

ensure_env_file() {
  if [[ ! -f "${ENV_FILE}" ]]; then
    echo "ERROR: .env not found at ${ENV_FILE}. Copy .env.example to .env." >&2
    exit 1
  fi
}

load_env() {
  ensure_env_file
  # shellcheck disable=SC1090
  set -a; . "${ENV_FILE}"; set +a
}

# Returns 0 when the bundled redis-stack should be used (REDIS_URL is empty
# or already points at the in-network service); 1 for any external URL.
needs_local_redis() {
  local url="${REDIS_URL:-}"
  if [[ -z "${url}" ]]; then return 0; fi
  case "${url}" in
    redis://redis-stack*|rediss://redis-stack*) return 0 ;;
    *) return 1 ;;
  esac
}

# Sets REDIS_URL + COMPOSE_PROFILES for the rest of the script session so
# every compose call sees the right wiring. Idempotent.
#
# AGENT_MODE is intentionally NOT forced here — the backend auto-detects
# per-service (Wave 8b): ANTHROPIC_API_KEY present → real Claude, absent →
# MockClaudeClient (canned SSE traces). Setting AGENT_MODE in .env still
# wins and accepts ``claude`` / ``stub`` / ``mock``.
configure_redis_mode() {
  load_env
  if needs_local_redis; then
    export REDIS_URL="${LOCAL_REDIS_URL}"
    REDIS_MODE="bundled"
    _append_profile "local-redis"
  else
    REDIS_MODE="external"
  fi
  export REDIS_MODE
}

_append_profile() {
  local p="$1"
  if [[ -z "${COMPOSE_PROFILES:-}" ]]; then
    export COMPOSE_PROFILES="${p}"
  elif [[ ",${COMPOSE_PROFILES}," != *",${p},"* ]]; then
    export COMPOSE_PROFILES="${COMPOSE_PROFILES},${p}"
  fi
}

# Compose wrapper — prepends the standard --env-file/-f flags so callers
# only have to think about the subcommand.
compose() {
  docker compose -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" "$@"
}

# Wait for an HTTP endpoint to respond 2xx. Usage: wait_http <url> <seconds>.
wait_http() {
  local url="$1" seconds="${2:-60}" deadline
  deadline=$(( $(date +%s) + seconds ))
  while ! curl -fsS "${url}" >/dev/null 2>&1; do
    if (( $(date +%s) > deadline )); then
      echo "ERROR: ${url} did not respond within ${seconds}s" >&2
      return 1
    fi
    sleep 2
  done
}

# 4-hero deterministic verdict regression. Hits /agent/verdict-fast which
# is LLM-free, so this passes in both zero-config (stub agent) and
# presenter (Claude agent) modes.
verify_heroes_curl() {
  local hero expected body failures=0
  for hero in mike jane alex sarah; do
    case "${hero}" in
      mike|jane) expected="approve" ;;
      alex)      expected="block" ;;
      sarah)     expected="review" ;;
    esac
    body=$(curl -fsS -X POST http://localhost:8000/agent/verdict-fast \
      -H 'Content-Type: application/json' \
      -d "{\"customer_id\":\"cust_${hero}\"}" 2>/dev/null) || {
        echo "  ✗ ${hero}: backend not reachable" >&2
        failures=$((failures+1)); continue
    }
    if printf '%s' "${body}" | grep -q "\"verdict\":\"${expected}\""; then
      echo "  ✓ ${hero}: verdict=${expected}"
    else
      echo "  ✗ ${hero}: expected verdict=${expected}, got: ${body}" >&2
      failures=$((failures+1))
    fi
  done
  if (( failures > 0 )); then
    echo "  ${failures} hero(es) failed verdict check" >&2
    return 1
  fi
}
