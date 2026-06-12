"""Tests for the Wave 7n Redis verdict cache.

Two surfaces:

* :mod:`app.verdict_cache` module — write-on-miss, read-on-hit, clear-by-
  customer, clear-all, error-no-cache.
* :mod:`app.api.agent` /score and /score/stream — header semantics and
  stream replay timing.
"""

from __future__ import annotations

import asyncio
import json
import time

import fakeredis
import pytest
from fastapi.testclient import TestClient

from app import verdict_cache
from app.agent_tools import Backends
from app.api import deps as api_deps
from app.main import app
from app.stub_agent import StubAgent

from tests.test_stub_agent import FakeContextRetriever, FakePolicyRAG


# ---------- module-level helpers ------------------------------------------

def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro) if False else asyncio.run(coro)


def test_transaction_signature_is_stable_and_short():
    class Tx:
        def model_dump(self):
            return {"amount": 100, "currency": "USD", "merchant_id": "m1",
                    "country": "US", "device_id": "d1"}
    s1 = verdict_cache.transaction_signature(Tx())
    s2 = verdict_cache.transaction_signature(Tx())
    assert s1 == s2 and len(s1) == 12
    # Different field → different sig.
    class Tx2(Tx):
        def model_dump(self):
            return {**super().model_dump(), "amount": 999}
    assert verdict_cache.transaction_signature(Tx2()) != s1


def test_get_returns_none_on_miss():
    r = fakeredis.FakeRedis(decode_responses=True)
    assert asyncio.run(verdict_cache.get(r, "cust_mike", "abc")) is None


def test_put_then_get_roundtrips_and_sets_ttl():
    r = fakeredis.FakeRedis(decode_responses=True)
    payload = {"response": {"verdict": "approve"}, "events": [{"type": "step"}]}
    asyncio.run(verdict_cache.put(r, "cust_mike", "abc", payload, ttl_seconds=60))
    got = asyncio.run(verdict_cache.get(r, "cust_mike", "abc"))
    assert got == payload
    # TTL must be set — no unbounded keys.
    ttl = r.ttl("cache:agent:verdict:cust_mike:abc")
    assert 0 < ttl <= 60


def test_get_returns_none_on_decode_error():
    r = fakeredis.FakeRedis(decode_responses=True)
    r.set("cache:agent:verdict:cust_x:bad", "not-json{{")
    assert asyncio.run(verdict_cache.get(r, "cust_x", "bad")) is None


def test_clear_by_customer_scoped():
    r = fakeredis.FakeRedis(decode_responses=True)
    asyncio.run(verdict_cache.put(r, "cust_mike", "s1", {"v": 1}))
    asyncio.run(verdict_cache.put(r, "cust_mike", "s2", {"v": 2}))
    asyncio.run(verdict_cache.put(r, "cust_jane", "s3", {"v": 3}))
    cleared = asyncio.run(verdict_cache.clear(r, "cust_mike"))
    assert cleared == 2
    assert asyncio.run(verdict_cache.get(r, "cust_mike", "s1")) is None
    assert asyncio.run(verdict_cache.get(r, "cust_jane", "s3")) == {"v": 3}


def test_clear_all_scans_prefix_only():
    r = fakeredis.FakeRedis(decode_responses=True)
    asyncio.run(verdict_cache.put(r, "cust_mike", "s1", {"v": 1}))
    asyncio.run(verdict_cache.put(r, "cust_jane", "s2", {"v": 2}))
    # Unrelated key must survive.
    r.set("feat:card_x", "do not delete")
    cleared = asyncio.run(verdict_cache.clear(r, None))
    assert cleared == 2
    assert r.get("feat:card_x") == "do not delete"


# ---------- end-to-end via FastAPI TestClient -----------------------------

@pytest.fixture
def cached_client(monkeypatch):
    """StubAgent wired to a shared FakeRedis the cache also sees."""
    redis_client = fakeredis.FakeRedis(decode_responses=True)
    redis_client.hset("feat:card_mike_visa", mapping={
        "velocity_1h": "0", "velocity_24h": "2", "velocity_7d": "10",
        "amount_avg_30d": "12.5", "amount_max_24h": "40.0",
        "geo_entropy": "0.05", "new_device_24h": "0",
    })
    backends = Backends(
        redis_client=redis_client,
        ctx=FakeContextRetriever(),
        policy_rag=FakePolicyRAG(),
    )
    agent = StubAgent(backends)
    monkeypatch.setattr(api_deps, "_agent", agent)
    monkeypatch.setattr(api_deps, "_backends", backends)
    monkeypatch.setattr(api_deps, "_redis_client", redis_client)
    monkeypatch.setenv("REDIS_URL", "redis://fake/0")
    monkeypatch.setenv("AGENT_MODE", "stub")
    with TestClient(app) as client:
        yield client, redis_client
    monkeypatch.setattr(api_deps, "_agent", None)
    monkeypatch.setattr(api_deps, "_backends", None)
    monkeypatch.setattr(api_deps, "_redis_client", None)


def _body():
    return {"customer_id": "cust_mike", "transaction": {"amount": 6.75, "currency": "USD"}}



def test_score_first_call_misses_then_hits(cached_client):
    client, _r = cached_client
    body = _body()

    miss = client.post("/agent/score", json=body)
    assert miss.status_code == 200
    assert miss.headers.get("x-cache") == "MISS"
    assert miss.json().get("cached") is False

    hit = client.post("/agent/score", json=body)
    assert hit.headers.get("x-cache") == "HIT"
    payload = hit.json()
    assert payload["cached"] is True
    assert isinstance(payload.get("cache_latency_ms"), int)
    assert payload["verdict"] == miss.json()["verdict"]
    assert payload["reason"] == miss.json()["reason"]


def test_score_bypass_header_skips_cache_but_writes_through(cached_client):
    client, _r = cached_client
    body = _body()
    client.post("/agent/score", json=body)
    bypass = client.post("/agent/score", json=body, headers={"x-bypass-cache": "1"})
    assert bypass.headers.get("x-cache") == "BYPASS"
    assert bypass.json().get("cached") is False
    again = client.post("/agent/score", json=body)
    assert again.headers.get("x-cache") == "HIT"


def test_score_bypass_via_query_string(cached_client):
    client, _r = cached_client
    body = _body()
    client.post("/agent/score", json=body)
    r = client.post("/agent/score?nocache=1", json=body)
    assert r.headers.get("x-cache") == "BYPASS"


def test_cache_clear_all_endpoint(cached_client):
    client, redis_client = cached_client
    client.post("/agent/score", json={"customer_id": "cust_mike",
                                       "transaction": {"amount": 1, "currency": "USD"}})
    client.post("/agent/score", json={"customer_id": "cust_jane",
                                       "transaction": {"amount": 2, "currency": "SGD"}})
    keys = [k for k in redis_client.keys("cache:agent:verdict:*")]
    assert len(keys) >= 2
    resp = client.post("/agent/cache/clear", json={})
    assert resp.status_code == 200
    assert resp.json()["cleared"] >= 2
    assert not redis_client.keys("cache:agent:verdict:*")


def test_cache_clear_by_customer(cached_client):
    client, redis_client = cached_client
    client.post("/agent/score", json={"customer_id": "cust_mike",
                                       "transaction": {"amount": 1, "currency": "USD"}})
    client.post("/agent/score", json={"customer_id": "cust_jane",
                                       "transaction": {"amount": 2, "currency": "SGD"}})
    resp = client.post("/agent/cache/clear", json={"customer_id": "cust_mike"})
    assert resp.json()["cleared"] == 1
    # Filter out internal index bookkeeping SETs; only verdict entries
    # carry the ``:{customer_id}:`` segment.
    remaining = [
        k for k in redis_client.keys("cache:agent:verdict:*")
        if not k.startswith("cache:agent:verdict:index")
    ]
    assert all(":cust_jane:" in k for k in remaining)


def test_stream_replay_is_fast_on_cache_hit(cached_client):
    client, _r = cached_client
    body = _body()
    # First call: live stream populates the cache.
    r1 = client.post("/agent/score/stream", json=body)
    assert r1.status_code == 200
    assert r1.headers.get("x-cache") == "MISS"
    events1 = [json.loads(l) for l in r1.text.split("\n") if l.strip()]
    n_events = len(events1)
    assert any(e.get("type") == "final" for e in events1)

    # Second call: cached replay must complete fast (<500ms wall-clock).
    t0 = time.perf_counter()
    r2 = client.post("/agent/score/stream", json=body)
    elapsed_ms = (time.perf_counter() - t0) * 1000
    assert r2.status_code == 200
    assert r2.headers.get("x-cache") == "HIT"
    events2 = [json.loads(l) for l in r2.text.split("\n") if l.strip()]
    assert len(events2) == n_events
    final = next(e for e in events2 if e["type"] == "final")
    assert final["response"].get("cached") is True
    # 5ms × ~10 events ≈ 50ms; CI slack allows <500ms.
    assert elapsed_ms < 500, f"cached stream took {elapsed_ms:.0f}ms"


def test_stream_bypass_header_runs_live(cached_client):
    client, _r = cached_client
    body = _body()
    client.post("/agent/score/stream", json=body)
    r = client.post("/agent/score/stream", json=body, headers={"x-bypass-cache": "1"})
    assert r.headers.get("x-cache") == "BYPASS"
    events = [json.loads(l) for l in r.text.split("\n") if l.strip()]
    final = next(e for e in events if e["type"] == "final")
    assert final["response"].get("cached") is not True
