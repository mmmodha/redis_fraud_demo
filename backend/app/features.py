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
from typing import Deque, Optional

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


def get_features(card_id: str) -> dict:
    return get_store().get_features(card_id)
