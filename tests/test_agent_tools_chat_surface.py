"""Tests for the Wave 7e chat-context-surface tools.

Exercises ``get_devices_for_customer``, ``get_disputes`` and
``get_pending_review`` through the public ``call_tool`` dispatcher so the
trace contract and the underlying Redis reads are covered together.
``get_devices_for_customer`` is backed by the Context Retriever, while
``get_disputes`` / ``get_pending_review`` are direct Redis JSON reads on
the ``disputes:*`` / ``pending_review:*`` keys seeded by
``data.seed_memory``.
"""

from __future__ import annotations

import fakeredis
import pytest

from app.agent_tools import Backends, call_tool

from tests.test_stub_agent import FakeContextRetriever


@pytest.fixture
def client() -> fakeredis.FakeRedis:
    return fakeredis.FakeRedis(decode_responses=True)


@pytest.fixture
def backends(client: fakeredis.FakeRedis) -> Backends:
    return Backends(redis_client=client, ctx=FakeContextRetriever(), policy_rag=None)


# ---------- get_devices_for_customer --------------------------------------

async def test_get_devices_for_customer_delegates_to_context_retriever(backends):
    out, step = await call_tool(
        "get_devices_for_customer", {"customer_id": "cust_alex"}, backends=backends,
    )
    assert step.component == "context_retriever"
    assert step.tool == "get_devices_for_customer"
    # Trace input mirrors the underlying Context Retriever tool input shape
    # (``value`` is the auto-generated MCP field for customer_id).
    assert step.input == {"value": "cust_alex", "limit": 25}
    assert step.latency_ms >= 0
    # Fake CR echoes the underlying tool name into the payload — proves we
    # routed to the Context Retriever's filter_device_by_customer_id tool.
    fake_calls = backends.ctx.calls
    assert ("filter_device_by_customer_id", {"value": "cust_alex", "limit": 25}) in fake_calls


# ---------- get_disputes --------------------------------------------------

def _seed_disputes(client: fakeredis.FakeRedis) -> None:
    client.json().set("disputes:cust_alex", "$", {
        "customer_id": "cust_alex", "items": [],
    })
    client.json().set("disputes:cust_bg_0007", "$", {
        "customer_id": "cust_bg_0007",
        "items": [{
            "dispute_id": "disp_bg_0007_001",
            "transaction_id": "tx_bg_00042",
            "merchant_name": "Quasi-Cash Exchange Co.",
            "amount": 320.00, "currency": "USD",
            "opened_at": "2026-04-12T10:14:00Z",
            "status": "closed", "outcome": "refunded",
            "reason": "unauthorised",
        }],
    })


async def test_get_disputes_empty_for_clean_customer(backends):
    _seed_disputes(backends.redis_client)
    out, step = await call_tool(
        "get_disputes", {"customer_id": "cust_alex"}, backends=backends,
    )
    assert out == {"customer_id": "cust_alex", "days": 180, "items": [], "count": 0}
    assert step.component == "context_retriever"
    assert step.tool == "get_disputes"
    assert step.redis_keys_touched == ["disputes:cust_alex"]
    assert "0 dispute" in step.output_summary


async def test_get_disputes_returns_recent_records(backends):
    _seed_disputes(backends.redis_client)
    out, step = await call_tool(
        "get_disputes", {"customer_id": "cust_bg_0007", "days": 365},
        backends=backends,
    )
    assert out["count"] == 1
    assert out["items"][0]["merchant_name"] == "Quasi-Cash Exchange Co."
    assert out["items"][0]["outcome"] == "refunded"
    assert step.input == {"customer_id": "cust_bg_0007", "days": 365}


async def test_get_disputes_missing_customer_returns_empty(backends):
    out, step = await call_tool(
        "get_disputes", {"customer_id": "cust_does_not_exist"}, backends=backends,
    )
    assert out == {
        "customer_id": "cust_does_not_exist", "days": 180,
        "items": [], "count": 0,
    }
    assert step.redis_keys_touched == ["disputes:cust_does_not_exist"]


# ---------- get_pending_review --------------------------------------------

def _seed_pending_alex(client: fakeredis.FakeRedis) -> None:
    client.json().set("pending_review:cust_alex", "$", {
        "transaction_id": "tx_alex_pending_br_electronics",
        "customer_id": "cust_alex",
        "amount": 1240.00, "currency": "USD",
        "merchant_name": "MegaTech Eletronicos",
        "merchant_country": "BR",
        "merchant_category": "5732",
        "device_id": "dev_alex_unknown_android",
        "device_first_seen_today": True,
        "foreign_country": True,
        "impossible_travel": True,
        "occurred_at": "2026-06-11T12:00:00Z",
    })


async def test_get_pending_review_returns_queued_transaction(backends):
    _seed_pending_alex(backends.redis_client)
    out, step = await call_tool(
        "get_pending_review", {"customer_id": "cust_alex"}, backends=backends,
    )
    assert out["amount"] == 1240.00
    assert out["merchant_country"] == "BR"
    assert out["device_first_seen_today"] is True
    assert out["impossible_travel"] is True
    assert step.component == "context_retriever"
    assert step.tool == "get_pending_review"
    assert step.redis_keys_touched == ["pending_review:cust_alex"]
    assert "1240" in step.output_summary or "MegaTech" in step.output_summary


async def test_get_pending_review_returns_null_when_none(backends):
    out, step = await call_tool(
        "get_pending_review", {"customer_id": "cust_mike"}, backends=backends,
    )
    assert out is None
    assert step.output_summary == "no pending review"
    assert step.output_data == {"customer_id": "cust_mike", "pending": None}


# ---------- get_geo_entropy + pending review --------------------------------


async def test_get_geo_entropy_elevates_for_alex_pending_review(client, backends):
    """US-only feat hash + staged Brazil swipe must not read as geo_entropy=0."""
    client.hset("feat:card_alex_visa", mapping={"geo_entropy": "0.0", "new_device_24h": "0"})
    client.json().set(
        "pending_review:cust_alex",
        "$",
        {
            "customer_id": "cust_alex",
            "merchant_country": "BR",
            "foreign_country": True,
            "impossible_travel": True,
        },
    )
    out, step = await call_tool(
        "get_geo_entropy", {"customer_id": "cust_alex"}, backends=backends,
    )
    assert out["geo_entropy"] >= 0.91
    assert out["impossible_travel"] is True
    assert "impossible-travel" in step.output_summary
    assert step.component == "feature_store"
    assert step.tool == "get_geo_entropy"
