"""RDI status endpoint.

Reads the heartbeat doc written by the RDI processor at `rdi:status` and
returns the last observed Postgres→Redis replication lag for the UI panel.
"""
from __future__ import annotations

import json
import os

import redis
from fastapi import APIRouter

router = APIRouter(prefix="/rdi", tags=["rdi"])

HEARTBEAT_KEY = "rdi:status"


def _read_status() -> dict | None:
    url = os.environ.get("REDIS_URL", "")
    if not url:
        return None
    client = redis.Redis.from_url(url, socket_connect_timeout=2, socket_timeout=2)
    raw = client.execute_command("JSON.GET", HEARTBEAT_KEY)
    if not raw:
        return None
    return json.loads(raw)


@router.get("/status")
def rdi_status() -> dict:
    """Return last observed replication lag.

    ``lag_ms`` is the measured Postgres→Redis write delay reported by the
    processor on its most recent CDC event. ``None`` when the processor has
    not yet reported one (e.g. fresh stack, or older processor without the
    field) — the UI renders that as "Idle · caught up".
    """
    try:
        doc = _read_status()
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": exc.__class__.__name__}
    if not doc:
        return {"ok": False, "error": "no heartbeat"}

    raw_lag = doc.get("last_lag_ms")
    lag_ms = int(raw_lag) if isinstance(raw_lag, (int, float)) else None
    lag_seconds = lag_ms / 1000.0 if lag_ms is not None else None
    return {
        "ok": True,
        "lag_ms": lag_ms,
        "lag_seconds": lag_seconds,
        "events_total": doc.get("events_total"),
        "last_event_at": doc.get("last_event_at"),
        "last_heartbeat_at": doc.get("last_heartbeat_at"),
        "started_at": doc.get("started_at"),
    }
