#!/usr/bin/env bash
# Full verification: 4-hero deterministic curl regression + a Playwright
# sanity test executed inside the official Playwright container so the
# host needs no Node/npm/Chromium install. Non-zero on any failure.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=./_lib.sh
. "${SCRIPT_DIR}/_lib.sh"

configure_redis_mode

echo "==> 4-hero curl regression"
verify_heroes_curl

echo "==> Playwright sanity (in container)"
# Run a single hero scenario end-to-end against the live frontend +
# backend. Mounts ../frontend so the tests come along; node_modules is a
# named volume so the first install is the only slow one.
_append_profile "verify"
compose run --rm verifier

echo "✓ verify complete"
