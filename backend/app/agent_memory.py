"""Per-customer Agent Memory stored as RedisJSON at ``mem:{customer_id}``.

Schema and design notes live in ``docs/agent-memory.md``. All helpers take an
injected ``redis.Redis`` client so the same code path is exercised by the demo
backend, the seed script, and the test suite.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Iterable

import redis

KEY_PREFIX = "mem:"
SCAN_BATCH = 200

_LIST_FIELDS = (
    "travel_windows",
    "prior_disputes",
    "flagged_devices",
    "conversation_notes",
)


def _key(customer_id: str) -> str:
    if not customer_id:
        raise ValueError("customer_id is required")
    return f"{KEY_PREFIX}{customer_id}"


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _empty(customer_id: str) -> dict:
    return {
        "customer_id": customer_id,
        "travel_windows": [],
        "prior_disputes": [],
        "flagged_devices": [],
        "conversation_notes": [],
        "last_updated_at": _now_iso(),
    }


def _ensure(client: redis.Redis, customer_id: str) -> None:
    """Create the document with an empty skeleton if it does not exist.

    Uses ``JSON.SET ... NX`` so concurrent callers cannot race past each other
    and overwrite an existing doc.
    """
    client.json().set(_key(customer_id), "$", _empty(customer_id), nx=True)


def _bump_updated_at(client: redis.Redis, customer_id: str) -> None:
    client.json().set(_key(customer_id), "$.last_updated_at", _now_iso())


def _today() -> date:
    return datetime.now(timezone.utc).date()


def _filter_expired_windows(doc: dict) -> dict:
    today = _today()
    kept = []
    for win in doc.get("travel_windows", []):
        end = win.get("end_date")
        try:
            if end and date.fromisoformat(end) >= today:
                kept.append(win)
        except ValueError:
            # Malformed date — keep it so the operator notices, don't silently drop.
            kept.append(win)
    doc["travel_windows"] = kept
    return doc


def get_memory(client: redis.Redis, customer_id: str) -> dict:
    """Return the memory doc with expired travel windows filtered out.

    Returns a fresh empty skeleton (not persisted) for unknown customers so
    callers can treat the result as always-present.
    """
    raw = client.json().get(_key(customer_id), "$")
    if not raw:
        return _empty(customer_id)
    doc = raw[0] if isinstance(raw, list) else raw
    return _filter_expired_windows(doc)


def append_conversation_note(
    client: redis.Redis, customer_id: str, text: str, source: str = "agent"
) -> None:
    _ensure(client, customer_id)
    entry = {"timestamp": _now_iso(), "text": text, "source": source}
    client.json().arrappend(_key(customer_id), "$.conversation_notes", entry)
    _bump_updated_at(client, customer_id)


def add_travel_window(
    client: redis.Redis,
    customer_id: str,
    start_date: str,
    end_date: str,
    destinations: Iterable[str],
    source: str = "agent",
) -> None:
    # Validate ISO dates up front so bad data never reaches Redis.
    date.fromisoformat(start_date)
    date.fromisoformat(end_date)
    _ensure(client, customer_id)
    entry = {
        "start_date": start_date,
        "end_date": end_date,
        "destinations": list(destinations),
        "source": source,
    }
    client.json().arrappend(_key(customer_id), "$.travel_windows", entry)
    _bump_updated_at(client, customer_id)


def add_dispute(
    client: redis.Redis,
    customer_id: str,
    transaction_id: str,
    reason: str,
    resolution: str,
    dispute_date: str,
) -> None:
    date.fromisoformat(dispute_date)
    _ensure(client, customer_id)
    entry = {
        "transaction_id": transaction_id,
        "reason": reason,
        "resolution": resolution,
        "date": dispute_date,
    }
    client.json().arrappend(_key(customer_id), "$.prior_disputes", entry)
    _bump_updated_at(client, customer_id)


def add_flagged_device(
    client: redis.Redis, customer_id: str, device_id: str, reason: str
) -> None:
    _ensure(client, customer_id)
    entry = {"device_id": device_id, "reason": reason, "flagged_at": _now_iso()}
    client.json().arrappend(_key(customer_id), "$.flagged_devices", entry)
    _bump_updated_at(client, customer_id)


def purge_expired_travel_windows(
    client: redis.Redis, customer_id: str | None = None
) -> int:
    """Rewrite the travel_windows array in place, dropping past-end entries.

    When ``customer_id`` is ``None`` walks all ``mem:*`` keys with SCAN.
    Returns the number of windows removed across all touched documents.
    """
    removed = 0
    keys: Iterable[str]
    if customer_id is not None:
        keys = [_key(customer_id)]
    else:
        keys = (k.decode() if isinstance(k, bytes) else k
                for k in client.scan_iter(match=f"{KEY_PREFIX}*", count=SCAN_BATCH))
    for key in keys:
        raw = client.json().get(key, "$.travel_windows")
        if not raw:
            continue
        # Real Redis JSONPath returns ``[[...]]``; fakeredis sometimes unwraps
        # one layer to ``[...]``. Detect by looking at the inner element.
        if isinstance(raw, list) and raw and isinstance(raw[0], list):
            current = raw[0]
        else:
            current = raw
        if not isinstance(current, list):
            continue
        kept = []
        for win in current:
            end = win.get("end_date")
            try:
                if end and date.fromisoformat(end) >= _today():
                    kept.append(win)
                else:
                    removed += 1
            except ValueError:
                kept.append(win)
        if len(kept) != len(current):
            client.json().set(key, "$.travel_windows", kept)
            client.json().set(key, "$.last_updated_at", _now_iso())
    return removed


__all__ = [
    "KEY_PREFIX",
    "get_memory",
    "append_conversation_note",
    "add_travel_window",
    "add_dispute",
    "add_flagged_device",
    "purge_expired_travel_windows",
]
