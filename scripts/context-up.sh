#!/usr/bin/env bash
# Bootstrap Redis Context Retriever for the Fraud Command Center demo.
#
# Builds the one-shot bootstrap image, runs it with .env + backend/app
# mounted so the SDK can introspect ContextModel classes and write
# CTX_SURFACE_ID + CTX_AGENT_KEY back to the host .env. Then runs a sample
# tool call against the live surface to confirm end-to-end wiring.
#
# Secrets policy: this script never echoes CTX_ADMIN_KEY, CTX_AGENT_KEY,
# REDIS_URL, or REDIS_PASSWORD. Surface and tool IDs are not secret.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${REPO_ROOT}/.env"
IMAGE_TAG="fcc-context-retriever-bootstrap:local"

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "ERROR: .env not found at ${ENV_FILE}" >&2
  exit 1
fi

# shellcheck disable=SC1090
set -a; . "${ENV_FILE}"; set +a

if [[ -z "${CTX_ADMIN_KEY:-}" ]]; then
  echo "ERROR: CTX_ADMIN_KEY not set in .env (generate one in Redis Cloud > Context Retriever > Admin keys)." >&2
  exit 1
fi
if [[ -z "${REDIS_URL:-}" ]]; then
  echo "ERROR: REDIS_URL not set in .env." >&2
  exit 1
fi

echo "Building bootstrap image..."
docker build --quiet -t "${IMAGE_TAG}" "${REPO_ROOT}/infra/context-retriever" >/dev/null

echo "Running bootstrap (provisions surface + agent key; idempotent)..."
docker run --rm \
  -e CTX_ADMIN_KEY \
  -e REDIS_URL \
  -e CTX_ENV_FILE=/work/.env \
  -v "${ENV_FILE}:/work/.env" \
  -v "${REPO_ROOT}/backend:/work/backend:ro" \
  -v "${REPO_ROOT}/infra/context-retriever/bootstrap.py:/work/bootstrap.py:ro" \
  "${IMAGE_TAG}"

# Re-source the .env to pick up CTX_SURFACE_ID + CTX_AGENT_KEY just written.
set -a; . "${ENV_FILE}"; set +a

if [[ -z "${CTX_AGENT_KEY:-}" || -z "${CTX_SURFACE_ID:-}" ]]; then
  echo "ERROR: bootstrap did not write CTX_SURFACE_ID / CTX_AGENT_KEY to .env" >&2
  exit 1
fi

echo
echo "Tool catalog (ctxctl tools list --agent-key <redacted>):"
docker run --rm -e CTX_AGENT_KEY "${IMAGE_TAG}" \
  --entrypoint ctxctl 2>/dev/null || true
# The image's default entrypoint is bootstrap.py; override it to run ctxctl.
docker run --rm \
  -e CTX_AGENT_KEY \
  --entrypoint ctxctl \
  "${IMAGE_TAG}" \
  tools list --agent-key "${CTX_AGENT_KEY}" || {
    echo "WARN: ctxctl tools list failed; the SDK call inside bootstrap is the source of truth." >&2
  }

echo
echo "Sample tool call (fetch customer cust_mike):"
docker run --rm \
  -e CTX_AGENT_KEY \
  --entrypoint python \
  -v "${REPO_ROOT}/infra/context-retriever/sample_call.py:/work/sample_call.py:ro" \
  "${IMAGE_TAG}" \
  /work/sample_call.py cust_mike || {
    echo "WARN: sample tool call failed — surface may still be indexing." >&2
  }

echo
echo "context-up complete. CTX_SURFACE_ID and CTX_AGENT_KEY are in .env (redacted)."
