"""CLI for ``make policy-index``: build the RediSearch policy index.

Loads ``REDIS_URL`` from the environment (the Makefile target sources ``.env``
before calling), then drops and recreates ``idx:policies`` from the markdown
files under ``data/policies/``. Idempotent — safe to re-run after a corpus
update.

Never echoes the connection URL or any other secret.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import redis

# Allow ``python scripts/build_policy_index.py`` from the repo root by putting
# the backend dir on sys.path so ``import app.policy_rag`` resolves.
ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.policy_rag import build_index  # noqa: E402


def main() -> int:
    url = os.environ.get("REDIS_URL", "").strip()
    if not url:
        print("ERROR: REDIS_URL is not set (export it or run via `make policy-index`).",
              file=sys.stderr)
        return 1

    policy_dir = ROOT / "data" / "policies"
    if not policy_dir.is_dir():
        print(f"ERROR: policy dir not found: {policy_dir}", file=sys.stderr)
        return 1

    client = redis.Redis.from_url(
        url, decode_responses=False,
        socket_timeout=10, socket_connect_timeout=10,
    )
    try:
        client.ping()
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: cannot reach Redis ({type(exc).__name__}).", file=sys.stderr)
        return 2

    print(f"Building policy index from {policy_dir} …")
    stats = build_index(client, policy_dir)
    print(f"Indexed {stats['chunks']} chunk(s) across {stats['docs']} document(s) "
          f"into 'idx:policies'.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
