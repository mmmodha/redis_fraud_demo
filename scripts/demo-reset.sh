#!/usr/bin/env bash
# Full teardown: containers + named volumes (postgres data, redis-stack
# data, verifier node_modules cache) + orphans. External managed Redis is
# never touched — wiping a Redis Cloud database is not ours to do.
# Target runtime: < 30s.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=./_lib.sh
. "${SCRIPT_DIR}/_lib.sh"

configure_redis_mode

echo "Stack down (containers + named volumes)..."
# Activate every profile so `down` sweeps services that wouldn't normally
# be enumerated by the default profile.
COMPOSE_PROFILES="local-redis,seed,verify" \
  compose down -v --remove-orphans --timeout 5

echo "✓ reset complete"
