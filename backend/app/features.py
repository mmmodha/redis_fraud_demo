"""Per-card feature read API + read-latency ring buffer.

Reads land as a single HGETALL on ``feat:{card_id}`` so the call path is one
Redis round trip. Each call appends its elapsed time (ms) to a bounded deque
which the ``/health/features`` endpoint summarises as p50/p99/max.
"""

from __future__ import annotations

import os
import time
from collections import deque
from threading import Lock
from typing import Any, Deque, Optional

import redis


_INT_FIELDS = {"velocity_1h", "velocity_24h", "velocity_7d", "new_device_24h"}
_FLOAT_FIELDS = {"amount_avg_30d", "amount_max_24h", "geo_entropy", "last_updated_at"}

_RING_SIZE = 1024


def feat_key(card_id: str) -> str:
    return f"feat:{card_id}"


def _percentile(sorted_values: list[float], q: float) -> float:
    if not sorted_values:
        return 0.0
    k = (len(sorted_values) - 1) * (q / 100.0)
    f = int(k)
    c = min(f + 1, len(sorted_values) - 1)
    if f == c:
        return float(sorted_values[f])
    lo = float(sorted_values[f])
    hi = float(sorted_values[c])
    return lo + (hi - lo) * (k - f)


def _coerce(raw: dict) -> dict:
    out: dict = {}
    for k, v in raw.items():
        if k in _INT_FIELDS:
            try:
                out[k] = int(float(v))
            except (TypeError, ValueError):
                out[k] = 0
        elif k in _FLOAT_FIELDS:
            try:
                out[k] = float(v)
            except (TypeError, ValueError):
                out[k] = 0.0
        else:
            out[k] = v
    return out


class FeatureStore:
    """Thin Redis wrapper that times every read."""

    def __init__(self, client: redis.Redis) -> None:
        self._client = client
        self._latencies: Deque[float] = deque(maxlen=_RING_SIZE)
        self._lock = Lock()

    @classmethod
    def from_url(cls, url: str) -> "FeatureStore":
        client = redis.Redis.from_url(
            url, decode_responses=True,
            socket_timeout=2, socket_connect_timeout=2,
        )
        return cls(client)

    def get_features(self, card_id: str) -> dict:
        start = time.perf_counter()
        raw = self._client.hgetall(feat_key(card_id))
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        with self._lock:
            self._latencies.append(elapsed_ms)
        return _coerce(raw)

    def latency_summary(self) -> dict:
        with self._lock:
            samples = list(self._latencies)
        if not samples:
            return {"count": 0, "p50_ms": None, "p99_ms": None, "max_ms": None}
        s = sorted(samples)
        return {
            "count": len(s),
            "p50_ms": round(_percentile(s, 50), 3),
            "p99_ms": round(_percentile(s, 99), 3),
            "max_ms": round(s[-1], 3),
        }

    def reset_latencies(self) -> None:
        with self._lock:
            self._latencies.clear()


_store: Optional[FeatureStore] = None


def get_store() -> FeatureStore:
    """Process-wide singleton; lazy so missing REDIS_URL fails on first use."""
    global _store
    if _store is None:
        url = os.environ.get("REDIS_URL", "")
        if not url:
            raise RuntimeError("REDIS_URL is not set")
        _store = FeatureStore.from_url(url)
    return _store


def pending_review_key(customer_id: str) -> str:
    return f"pending_review:{customer_id}"


def read_pending_review(client: redis.Redis, customer_id: str) -> Optional[dict[str, Any]]:
    raw = client.json().get(pending_review_key(customer_id), "$")
    if not raw:
        return None
    payload = raw[0] if isinstance(raw, list) else raw
    return payload if isinstance(payload, dict) else None


def overlay_pending_fraud_signals(features: dict, pending: Optional[dict[str, Any]]) -> dict:
    """Adjust feat:* reads for in-flight swipes staged in pending_review.

    Settled history for Alex is US-only (geo_entropy=0) until the Brazil
    electronics attempt lands in the stream; the demo stages that swipe as
    pending so presenters see the fraud signal on the Feature Store panel.
    """
    if not pending:
        return features
    out = dict(features)
    if pending.get("impossible_travel") or pending.get("foreign_country"):
        out["geo_entropy"] = max(float(out.get("geo_entropy", 0.0) or 0.0), 0.91)
        out["impossible_travel"] = True
    if pending.get("device_first_seen_today"):
        out["new_device_24h"] = max(int(out.get("new_device_24h", 0) or 0), 1)
    return out


def get_features(card_id: str, *, customer_id: Optional[str] = None) -> dict:
    store = get_store()
    data = store.get_features(card_id)
    if customer_id:
        pending = read_pending_review(store._client, customer_id)
        data = overlay_pending_fraud_signals(data, pending)
    return data


def get_features_raw(card_id: str) -> dict:
    """HGETALL on feat:{card_id} without pending-review overlay."""
    return get_store().get_features(card_id)
