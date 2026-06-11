#!/usr/bin/env bash
# Capture all six PNGs used by README.md and docs/runbook.md.
#
# Output (overwritten on each run):
#   docs/screenshots/command-center.png        — default (jane) scenario
#   docs/screenshots/hero-mike.png             — Mike scenario, full page
#   docs/screenshots/hero-jane.png             — Jane scenario, full page
#   docs/screenshots/hero-alex.png             — Alex scenario, full page
#   docs/screenshots/chatbot-comparison.png    — RAG vs IRIS side-by-side
#   docs/screenshots/iris-panels-detail.png    — close-up of the IRIS rail
#
# Assumes the demo stack is already running (run `make demo` first). The
# Playwright config will reuse an existing dev server on :3030 OR connect
# to whatever PLAYWRIGHT_BASE_URL points to.
#
# By default we target the Docker frontend on http://localhost:3000 so the
# screenshots reflect the production build. Override with FRONTEND_URL.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}/frontend"

FRONTEND_URL="${FRONTEND_URL:-http://localhost:3000}"

echo "Capturing screenshots against ${FRONTEND_URL}..."
echo "  (output → docs/screenshots/)"

# Quick reachability check so we fail fast with a clear message instead of
# letting Playwright spin up its own dev server.
if ! curl -fsS "${FRONTEND_URL}/" >/dev/null 2>&1; then
  echo "ERROR: ${FRONTEND_URL} is not reachable." >&2
  echo "Run \`make demo\` first, or set FRONTEND_URL to a running instance." >&2
  exit 1
fi

# Install Playwright browser binary if missing (idempotent, fast on re-run).
npx playwright install --with-deps chromium >/dev/null 2>&1 || true

# Derive the port from FRONTEND_URL so playwright.config.ts reuses the
# already-running server (reuseExistingServer:true) instead of spawning
# its own Next.js dev process.
FRONTEND_PORT="$(echo "${FRONTEND_URL}" | sed -E 's#https?://[^:/]+:?([0-9]*).*#\1#')"
FRONTEND_PORT="${FRONTEND_PORT:-3000}"

PLAYWRIGHT_BASE_URL="${FRONTEND_URL}" \
FRONTEND_PORT="${FRONTEND_PORT}" \
  npx playwright test \
    tests/hero-scenarios.spec.ts \
    tests/chatbot-compare.spec.ts \
    tests/capture-screenshots.spec.ts \
  --reporter=line

echo ""
echo "Screenshots written:"
ls -1 "${ROOT_DIR}/docs/screenshots/"
