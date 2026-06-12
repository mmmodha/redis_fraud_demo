"""Tests for the deterministic stub fraud agent.

Each hero customer must return its expected verdict and the resulting
``AgentTrace`` must contain calls to the components / tools the demo
narrative depends on, in the documented order. We exercise the real
``call_tool`` dispatcher against fake backends so any drift between the
schemas, the dispatcher, and the stub will fail here.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

import fakeredis
import pytest

from app.agent_tools import Backends
from app.context_retriever import TraceRecord
from app.schemas import TransactionPayload
from app.stub_agent import LLM_MODEL, StubAgent


# ---------- fakes ----------------------------------------------------------

@dataclass
class _FakeChunk:
    chunk_id: str
    doc_id: str
    title: str
    text: str


class FakePolicyRAG:
    """Trivial PolicyRAG stand-in: always returns the same three canned chunks."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, int]] = []

    def search(self, query: str, k: int = 5):
        self.calls.append((query, k))
        from app.schemas import TraceStep
        chunks = [
            {"chunk_id": "fake-001", "doc_id": "policy", "title": "Foreign Travel",
             "text": "Travel windows widen the velocity tolerance."},
            {"chunk_id": "fake-002", "doc_id": "policy", "title": "New Device",
             "text": "First-seen devices require step-up auth above $500."},
            {"chunk_id": "fake-003", "doc_id": "policy", "title": "Velocity",
             "text": "1h velocity over 6 is anomalous for personal cards."},
        ][:k]
        step = TraceStep(
            component="policy_rag", tool="search_policy",
            input={"query": query, "k": k},
            output_summary=f"{len(chunks)} chunk(s)",
            output_data={"chunks": chunks},
            latency_ms=1, redis_keys_touched=["idx:policies"],
        )
        return chunks, step


class FakeContextRetriever:
    """Records every tool invocation and returns canned MCP-shaped payloads."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    async def _call(self, tool: str, args: dict[str, Any]):
        self.calls.append((tool, dict(args)))
        result = {"content": [{"type": "text", "text": f"fake[{tool}]({args})"}]}
        trace = TraceRecord(tool=tool, input=dict(args),
                            output_summary=f"fake {tool}", latency_ms=2)
        return result, trace

    async def get_recent_transactions(self, customer_id, days=30, limit=25):
        result, t = await self._call("filter_transaction_by_customer_id",
                                     {"value": customer_id, "limit": limit})
        t.input["days"] = days
        return result, t

    async def search_similar_transactions(self, query, k=5):
        return await self._call("search_transaction_by_text", {"query": query, "limit": k})

    async def merchant_reputation(self, merchant_id):
        return await self._call("get_merchant_by_id", {"id": merchant_id})

    async def devices_seen_for_customer(self, customer_id, limit=25):
        return await self._call("filter_device_by_customer_id",
                                {"value": customer_id, "limit": limit})


@pytest.fixture
def redis_client():
    return fakeredis.FakeRedis(decode_responses=True)


@pytest.fixture
def seeded_redis(redis_client):
    # Seed feature hashes for the three hero cards.
    redis_client.hset("feat:card_mike_visa", mapping={
        "velocity_1h": "0", "velocity_24h": "2", "velocity_7d": "10",
        "amount_avg_30d": "12.5", "amount_max_24h": "40.0",
        "geo_entropy": "0.05", "new_device_24h": "0",
    })
    redis_client.hset("feat:card_jane_visa", mapping={
        "velocity_1h": "1", "velocity_24h": "3", "velocity_7d": "15",
        "amount_avg_30d": "60.0", "amount_max_24h": "200.0",
        "geo_entropy": "0.45", "new_device_24h": "0",
    })
    redis_client.hset("feat:card_alex_visa", mapping={
        "velocity_1h": "4", "velocity_24h": "8", "velocity_7d": "20",
        "amount_avg_30d": "80.0", "amount_max_24h": "2400.0",
        "geo_entropy": "0.91", "new_device_24h": "1",
    })
    # Alex: alleged new device is genuinely never seen on this card.
    redis_client.hset("feat:_dev:card_alex_visa", mapping={
        "dev_alex_macbook": "2026-01-01T00:00:00Z",
    })
    # Jane: declared travel window via agent memory.
    redis_client.json().set("mem:cust_jane", "$", {
        "customer_id": "cust_jane",
        "travel_windows": [
            {"start_date": "2099-11-10", "end_date": "2099-11-17",
             "destinations": ["Singapore"], "source": "seed"},
        ],
        "prior_disputes": [], "flagged_devices": [], "conversation_notes": [],
        "last_updated_at": "2026-06-11T00:00:00Z",
    })
    return redis_client


@pytest.fixture
def backends(seeded_redis):
    return Backends(
        redis_client=seeded_redis,
        ctx=FakeContextRetriever(),
        policy_rag=FakePolicyRAG(),
    )


@pytest.fixture
def agent(backends):
    return StubAgent(backends)


# ---------- per-hero verdicts ---------------------------------------------

def _components(trace) -> list[str]:
    return [s.component for s in trace.steps]


def _tools(trace) -> list[str]:
    return [s.tool for s in trace.steps]


async def test_mike_clean_approves(agent):
    resp = await agent.score("cust_mike", TransactionPayload(
        amount=6.75, currency="USD", merchant_id="merch_mike_coffee", country="US"))
    assert resp.verdict == "approve"
    assert resp.confidence == pytest.approx(0.92)
    assert "velocity" in resp.reason.lower()
    assert resp.trace.llm_model == LLM_MODEL
    assert _tools(resp.trace) == [
        "get_customer_context", "get_velocity_features", "search_policy",
    ]
    assert _components(resp.trace) == [
        "context_retriever", "feature_store", "policy_rag",
    ]


async def test_jane_near_miss_approves_with_memory(agent):
    resp = await agent.score("cust_jane", TransactionPayload(
        amount=480, currency="SGD", merchant_id="merch_jane_boutique_sg", country="SG"))
    assert resp.verdict == "approve"
    assert resp.confidence == pytest.approx(0.78)
    tools = _tools(resp.trace)
    # Order matters: context → recent → memory → merchant → policy.
    assert tools == [
        "get_customer_context", "get_recent_transactions",
        "get_customer_memory", "get_merchant_reputation", "search_policy",
    ]
    # Memory lookup must drive the reason.
    assert "Singapore" in resp.reason
    assert "agent_memory" in _components(resp.trace)
    # The agent_memory step must record the right Redis key.
    mem_step = next(s for s in resp.trace.steps if s.component == "agent_memory")
    assert mem_step.redis_keys_touched == ["mem:cust_jane"]


async def test_alex_fraud_blocks(agent):
    resp = await agent.score("cust_alex", TransactionPayload(
        amount=2400, currency="USD", merchant_id="merch_alex_electronics_br",
        country="BR", device_id="dev_alex_unknown_android"))
    assert resp.verdict == "block"
    assert resp.confidence == pytest.approx(0.94)
    tools = _tools(resp.trace)
    assert tools == [
        "get_customer_context", "get_devices_for_customer",
        "get_new_device_flag", "get_geo_entropy", "find_similar_fraud",
        "search_policy",
    ]
    # The new-device feature step must observe the device is NOT known.
    nd_step = next(s for s in resp.trace.steps if s.tool == "get_new_device_flag")
    assert nd_step.output_data["device_known_to_card"] is False
    assert nd_step.output_data["new_device_24h"] is True


async def test_generic_customer_returns_review(agent):
    resp = await agent.score("cust_unknown", TransactionPayload(
        amount=10, currency="USD", card_id="card_other"))
    assert resp.verdict == "review"
    assert 0.0 <= resp.confidence <= 1.0
    # Always at least one context lookup, plus a policy lookup.
    assert "get_customer_context" in _tools(resp.trace)
    assert "search_policy" in _tools(resp.trace)


async def test_trace_latency_fields_are_non_negative(agent):
    resp = await agent.score("cust_mike", TransactionPayload(amount=1, currency="USD"))
    assert resp.trace.total_latency_ms >= 0
    assert all(s.latency_ms >= 0 for s in resp.trace.steps)
    assert resp.trace.steps, "score must produce at least one trace step"
