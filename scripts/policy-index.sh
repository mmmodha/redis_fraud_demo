#!/usr/bin/env bash
# Rebuild the RediSearch idx:policies index from data/policies/*.md.
# Runs inside the already-running backend container (so we reuse its
# sentence-transformers install). Idempotent — FT.DROPINDEX before
# FT.CREATE inside `build_index()`.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=./_lib.sh
. "${SCRIPT_DIR}/_lib.sh"

configure_redis_mode

compose exec -T backend python - <<'PY'
import os, sys, redis
sys.path.insert(0, "/app")
from app.policy_rag import build_index
url = os.environ.get("REDIS_URL", "").strip()
if not url:
    sys.exit("REDIS_URL is not set in backend container")
client = redis.Redis.from_url(
    url, decode_responses=False, socket_timeout=30, socket_connect_timeout=10,
)
client.ping()
stats = build_index(client, "/policies")
print(f"indexed {stats['chunks']} chunk(s) across {stats['docs']} doc(s)")
PY
