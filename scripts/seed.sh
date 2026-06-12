#!/usr/bin/env bash
# Container-only seed pipeline:
#   1. data.seed         — Postgres schema + 10k transactions + heroes.
#   2. data.seed_memory  — Redis agent memory / disputes / pending review.
#   3. policy index      — RediSearch idx:policies built inside backend.
# Each step is idempotent (NX writes, FT.DROPINDEX before FT.CREATE).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=./_lib.sh
. "${SCRIPT_DIR}/_lib.sh"

configure_redis_mode
_append_profile "seed"

echo "  seed: bank schema + transactions"
compose run --rm seeder python -m data.seed

echo "  seed: agent memory + disputes + pending review"
compose run --rm seeder python -m data.seed_memory

echo "  seed: RediSearch policy index"
"${SCRIPT_DIR}/policy-index.sh" | sed 's/^/    /'

echo "  seeds complete"
