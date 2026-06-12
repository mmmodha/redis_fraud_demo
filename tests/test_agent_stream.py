"""Tests for the streaming agent endpoint (Wave 7j).

Exercises ``/agent/score/stream`` end-to-end against the deterministic
``StubAgent`` so the assertions don't require an Anthropic key. Validates:

* NDJSON line-per-event framing,
* event ordering: ``thinking → step* → final``,
* final ``ScoreResponse`` parity with the non-streaming ``/agent/score`` for
  the same input,
* presence of ``X-Accel-Buffering: no`` so proxies don't coalesce chunks.
"""

from __future__ import annotations

import json
import os

import fakeredis
import pytest
from fastapi.testclient import TestClient

from app.agent_tools import Backends
from app.api import deps as api_deps
from app.main import app
from app.stub_agent import StubAgent

from tests.test_stub_agent import FakeContextRetriever, FakePolicyRAG


@pytest.fixture
def stub_agent_client(monkeypatch):
    """Force the API to use a StubAgent wired to in-memory fakes."""
    redis_client = fakeredis.FakeRedis(decode_responses=True)
    # Mirror the same Mike/Jane/Alex feature seeding used in test_stub_agent.
    redis_client.hset("feat:card_mike_visa", mapping={
        "velocity_1h": "0", "velocity_24h": "2", "velocity_7d": "10",
        "amount_avg_30d": "12.5", "amount_max_24h": "40.0",
        "geo_entropy": "0.05", "new_device_24h": "0",
    })
    redis_client.json().set("mem:cust_jane", "$", {
        "customer_id": "cust_jane",
        "travel_windows": [
            {"start_date": "2099-11-10", "end_date": "2099-11-17",
             "destinations": ["Singapore"], "source": "seed"},
        ],
        "prior_disputes": [], "flagged_devices": [], "conversation_notes": [],
        "last_updated_at": "2026-06-11T00:00:00Z",
    })
    backends = Backends(
        redis_client=redis_client,
        ctx=FakeContextRetriever(),
        policy_rag=FakePolicyRAG(),
    )
    agent = StubAgent(backends)

    # Force-resolve to our agent regardless of AGENT_MODE / ANTHROPIC_API_KEY.
    monkeypatch.setattr(api_deps, "_agent", agent)
    monkeypatch.setattr(api_deps, "_backends", backends)
    monkeypatch.setenv("AGENT_MODE", "stub")

    with TestClient(app) as client:
        yield client

    # Reset the module-level singletons so other tests are unaffected.
    monkeypatch.setattr(api_deps, "_agent", None)
    monkeypatch.setattr(api_deps, "_backends", None)


def _parse_ndjson(body: str) -> list[dict]:
    return [json.loads(line) for line in body.split("\n") if line.strip()]


def test_stream_emits_thinking_then_steps_then_final(stub_agent_client):
    resp = stub_agent_client.post(
        "/agent/score/stream",
        json={"customer_id": "cust_mike", "transaction": {"amount": 6.75, "currency": "USD"}},
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/x-ndjson")
    assert resp.headers.get("x-accel-buffering") == "no"

    events = _parse_ndjson(resp.text)
    assert events, "stream produced no events"
    types = [e["type"] for e in events]

    # Order: at least one "thinking", then ≥1 "step", terminating with "final".
    assert types[0] == "thinking", f"first event must be thinking, got {types[0]}"
    assert types[-1] == "final", f"last event must be final, got {types[-1]}"
    assert "step" in types, "stream must include at least one step event"

    # No step may appear before the first thinking event.
    first_step_idx = types.index("step")
    first_thinking_idx = types.index("thinking")
    assert first_thinking_idx < first_step_idx


def test_stream_step_events_match_trace_step_schema(stub_agent_client):
    resp = stub_agent_client.post(
        "/agent/score/stream",
        json={"customer_id": "cust_jane",
              "transaction": {"amount": 480, "currency": "SGD",
                              "merchant_id": "merch_jane_boutique_sg", "country": "SG"}},
    )
    events = _parse_ndjson(resp.text)
    step_events = [e for e in events if e["type"] == "step"]
    assert step_events, "expected at least one step event for cust_jane"
    for ev in step_events:
        step = ev["step"]
        # Required TraceStep fields per backend/app/schemas.py.
        for key in ("component", "tool", "input", "output_summary",
                    "latency_ms", "redis_keys_touched"):
            assert key in step, f"step missing {key}: {step}"
        assert step["component"] in (
            "context_retriever", "feature_store", "agent_memory",
            "policy_rag", "llm",
        )
        assert isinstance(step["latency_ms"], int) and step["latency_ms"] >= 0


def test_stream_final_matches_non_streaming_score(stub_agent_client):
    """The assembled final ScoreResponse must match what /agent/score returns
    for the same input (parity is the whole point of the refactor)."""
    body = {
        "customer_id": "cust_jane",
        "transaction": {"amount": 480, "currency": "SGD",
                        "merchant_id": "merch_jane_boutique_sg", "country": "SG"},
    }
    non_stream = stub_agent_client.post("/agent/score", json=body).json()
    stream_events = _parse_ndjson(
        stub_agent_client.post("/agent/score/stream", json=body).text,
    )
    final = next(e for e in stream_events if e["type"] == "final")["response"]

    assert final["verdict"] == non_stream["verdict"]
    assert final["confidence"] == pytest.approx(non_stream["confidence"])
    assert final["reason"] == non_stream["reason"]
    # Same trace shape: same tool sequence (latency timings will differ).
    assert (
        [s["tool"] for s in final["trace"]["steps"]]
        == [s["tool"] for s in non_stream["trace"]["steps"]]
    )
    assert (
        [s["component"] for s in final["trace"]["steps"]]
        == [s["component"] for s in non_stream["trace"]["steps"]]
    )


def test_stream_step_events_in_same_order_as_final_trace(stub_agent_client):
    resp = stub_agent_client.post(
        "/agent/score/stream",
        json={"customer_id": "cust_alex",
              "transaction": {"amount": 2400, "currency": "USD",
                              "merchant_id": "merch_alex_electronics_br",
                              "country": "BR",
                              "device_id": "dev_alex_unknown_android"}},
    )
    events = _parse_ndjson(resp.text)
    streamed_tools = [e["step"]["tool"] for e in events if e["type"] == "step"]
    final = next(e for e in events if e["type"] == "final")["response"]
    final_tools = [s["tool"] for s in final["trace"]["steps"]]
    assert streamed_tools == final_tools
