"""One-shot Agent Memory seeder: Postgres ``customer_memory_seed`` → Redis ``mem:*``.

Runs after ``data.seed`` (which writes the Postgres source) and is independent
of RDI (RDI does not touch ``mem:*`` keys — see ``docs/agent-memory.md``).

Idempotent: skips customers whose ``mem:{id}`` key already exists in Redis so
re-running after a partial demo run is safe.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone

import redis

from data.db import cursor


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _canonicalise(customer_id: str, source: dict) -> dict:
    """Map the data-generator's seed shape onto the canonical Agent Memory schema.

    The generator wrote ``{"notes": [{text, source, tags}], "travel_window":
    {start, end, destination}}``. The canonical schema uses ``travel_windows``
    (list) and ``conversation_notes`` (list). See ``docs/agent-memory.md``.
    """
    travel_windows = []
    tw = source.get("travel_window")
    if tw and tw.get("start") and tw.get("end"):
        dest = tw.get("destination")
        travel_windows.append({
            "start_date": tw["start"],
            "end_date": tw["end"],
            "destinations": [dest] if isinstance(dest, str) else list(dest or []),
            "source": "seed",
        })
    conversation_notes = []
    for note in source.get("notes", []) or []:
        text = note.get("text")
        if not text:
            continue
        conversation_notes.append({
            "timestamp": _now_iso(),
            "text": text,
            "source": note.get("source", "seed"),
        })
    return {
        "customer_id": customer_id,
        "travel_windows": travel_windows,
        "prior_disputes": [],
        "flagged_devices": [],
        "conversation_notes": conversation_notes,
        "last_updated_at": _now_iso(),
    }


def _redis_client() -> redis.Redis:
    url = os.environ.get("REDIS_URL")
    if not url:
        raise SystemExit("REDIS_URL is not set — cannot seed Agent Memory.")
    return redis.Redis.from_url(url)


def seed(client: redis.Redis | None = None) -> dict[str, int]:
    """Walk ``customer_memory_seed`` and JSON.SET each row into Redis with NX.

    Returns counts for logging: ``{"written": N, "skipped": N}``.
    """
    client = client or _redis_client()
    written = 0
    skipped = 0
    with cursor() as (_conn, cur):
        cur.execute("SELECT customer_id, memory_json FROM customer_memory_seed")
        rows = cur.fetchall()
    for customer_id, memory_json in rows:
        # psycopg2 returns JSONB as dict already; tolerate str just in case.
        source = memory_json if isinstance(memory_json, dict) else json.loads(memory_json)
        canonical = _canonicalise(customer_id, source)
        ok = client.json().set(f"mem:{customer_id}", "$", canonical, nx=True)
        if ok:
            written += 1
        else:
            skipped += 1
    return {"written": written, "skipped": skipped}


def main() -> None:
    result = seed()
    print(f"agent-memory seeded: written={result['written']} skipped={result['skipped']}")


if __name__ == "__main__":
    main()
