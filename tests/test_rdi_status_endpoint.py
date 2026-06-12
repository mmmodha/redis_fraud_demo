"""Endpoint-layer tests for ``GET /rdi/status``.

The endpoint reads the heartbeat doc at ``rdi:status`` and must expose the
last observed replication lag in milliseconds (``lag_ms``). When the
processor hasn't reported one (older processor / fresh start), the
response must degrade gracefully to ``lag_ms = None`` instead of falling
back to the old "seconds since last CDC event" formula.
"""

from __future__ import annotations

import json

import fakeredis
import pytest

from backend.app import rdi as rdi_module


class _JsonGetShim:
    """Wraps fakeredis so ``execute_command('JSON.GET', ...)`` returns a JSON
    string (matching real Redis/RedisJSON), instead of fakeredis's parsed
    dict. The endpoint code calls ``json.loads`` on the result and an empty
    parsed dict would short-circuit the ``if not raw`` guard.
    """

    def __init__(self, inner: fakeredis.FakeRedis) -> None:
        self._inner = inner

    def execute_command(self, *args, **kwargs):
        if args and str(args[0]).upper() == "JSON.GET":
            value = self._inner.json().get(args[1])
            return None if value is None else json.dumps(value)
        return self._inner.execute_command(*args, **kwargs)


@pytest.fixture
def fake_redis(monkeypatch: pytest.MonkeyPatch) -> fakeredis.FakeRedis:
    inner = fakeredis.FakeRedis(decode_responses=True)
    shim = _JsonGetShim(inner)
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setattr(
        rdi_module.redis.Redis, "from_url", staticmethod(lambda *_a, **_k: shim)
    )
    return inner


def _write_doc(client: fakeredis.FakeRedis, doc: dict) -> None:
    client.json().set(rdi_module.HEARTBEAT_KEY, "$", doc)


def test_lag_ms_returned_when_heartbeat_has_it(fake_redis: fakeredis.FakeRedis) -> None:
    _write_doc(fake_redis, {
        "events_total": 1234,
        "last_event_at": "2026-06-12T10:00:00+00:00",
        "last_heartbeat_at": "2026-06-12T10:00:01+00:00",
        "last_lag_ms": 42,
        "started_at": "2026-06-12T09:59:00+00:00",
    })
    resp = rdi_module.rdi_status()
    assert resp["ok"] is True
    assert resp["lag_ms"] == 42
    # Backwards-compat field, computed from the same source.
    assert resp["lag_seconds"] == pytest.approx(0.042)
    assert resp["events_total"] == 1234


def test_lag_ms_is_null_when_heartbeat_missing_field(
    fake_redis: fakeredis.FakeRedis,
) -> None:
    # Simulates an older processor that hasn't been redeployed yet — the
    # endpoint must NOT fall back to the legacy "now - last_event_at" math.
    _write_doc(fake_redis, {
        "events_total": 99,
        "last_event_at": "2020-01-01T00:00:00+00:00",
        "last_heartbeat_at": "2026-06-12T10:00:00+00:00",
        "started_at": "2026-06-12T09:59:00+00:00",
    })
    resp = rdi_module.rdi_status()
    assert resp["ok"] is True
    assert resp["lag_ms"] is None
    assert resp["lag_seconds"] is None
    assert resp["events_total"] == 99


def test_lag_ms_handles_zero_value(fake_redis: fakeredis.FakeRedis) -> None:
    _write_doc(fake_redis, {
        "events_total": 1,
        "last_event_at": "2026-06-12T10:00:00+00:00",
        "last_heartbeat_at": "2026-06-12T10:00:00+00:00",
        "last_lag_ms": 0,
        "started_at": "2026-06-12T09:59:00+00:00",
    })
    resp = rdi_module.rdi_status()
    assert resp["lag_ms"] == 0
    assert resp["lag_seconds"] == 0.0


def test_no_heartbeat_returns_not_ok(
    fake_redis: fakeredis.FakeRedis,  # noqa: ARG001 — fixture wires env+client
) -> None:
    resp = rdi_module.rdi_status()
    assert resp["ok"] is False
    assert resp["error"] == "no heartbeat"
