"""RDI status endpoint.

Reads the heartbeat doc written by the RDI processor at `rdi:status` and
returns a lag metric the UI side panel can render.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone

import redis
from fastapi import APIRouter

router = APIRouter(prefix="/rdi", tags=["rdi"])

HEARTBEAT_KEY = "rdi:status"


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


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
    """Return current RDI sync lag.

    Lag = now - max(last_event_at, last_heartbeat_at).
    A null lag means the processor has never reported in.
    """
    try:
        doc = _read_status()
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": exc.__class__.__name__}
    if not doc:
        return {"ok": False, "error": "no heartbeat"}

    now = datetime.now(timezone.utc)
    last_event = _parse_iso(doc.get("last_event_at"))
    last_heartbeat = _parse_iso(doc.get("last_heartbeat_at"))
    reference = last_event or last_heartbeat
    lag_seconds = (now - reference).total_seconds() if reference else None
    return {
        "ok": True,
        "lag_seconds": lag_seconds,
        "events_total": doc.get("events_total"),
        "last_event_at": doc.get("last_event_at"),
        "last_heartbeat_at": doc.get("last_heartbeat_at"),
        "started_at": doc.get("started_at"),
    }
