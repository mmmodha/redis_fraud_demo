"""Smoke tests for ``backend.app.context_retriever.ContextRetriever``.

Runs against the live ``fraud-command-center`` surface and exercises one
call per public method for each of the three hero customers. Skips cleanly
if either:

* ``redis-context-retriever`` is not installed (e.g. local dev on
  Python 3.9 — the SDK requires 3.11+), or
* ``CTX_AGENT_KEY`` is not set in the environment (so CI / fresh checkouts
  don't hang on missing credentials).

Run after ``make context-up`` from a Python 3.11+ env::

    pip install -r backend/requirements-dev.txt
    pytest tests/test_context_retriever_client.py -v
"""

from __future__ import annotations

import asyncio
import os

import pytest

pytest.importorskip("context_surfaces")

if not os.environ.get("CTX_AGENT_KEY", "").strip():
    pytest.skip(
        "CTX_AGENT_KEY not set — run `make context-up` to provision the surface.",
        allow_module_level=True,
    )

from backend.app.context_retriever import ContextRetriever, TraceRecord  # noqa: E402

HEROES = ("cust_mike", "cust_jane", "cust_alex")


def _assert_trace(trace: TraceRecord, expected_tool: str) -> None:
    assert isinstance(trace, TraceRecord)
    assert trace.tool == expected_tool
    assert trace.latency_ms >= 0
    assert trace.input  # not empty
    assert trace.output_summary  # not empty


def _run_with_client(coro_factory):
    """Build a ContextRetriever in a fresh event loop, run one coroutine, exit.

    The MCP client's httpx pool is bound to the loop it was opened on, so
    each test owns its own ContextRetriever lifecycle.
    """

    async def _entry():
        async with ContextRetriever() as cr:
            return await coro_factory(cr)

    return asyncio.run(_entry())


@pytest.mark.parametrize("customer_id", HEROES)
def test_get_recent_transactions(customer_id):
    result, trace = _run_with_client(
        lambda cr: cr.get_recent_transactions(customer_id, days=60, limit=10)
    )
    _assert_trace(trace, "filter_transaction_by_customer_id")
    assert trace.input["value"] == customer_id
    assert "since" in trace.input
    assert result is not None


@pytest.mark.parametrize("customer_id", HEROES)
def test_devices_seen_for_customer(customer_id):
    result, trace = _run_with_client(lambda cr: cr.devices_seen_for_customer(customer_id))
    _assert_trace(trace, "filter_device_by_customer_id")
    assert trace.input["value"] == customer_id
    assert result is not None


def test_merchant_reputation():
    result, trace = _run_with_client(
        lambda cr: cr.merchant_reputation("merch_jane_boutique_sg")
    )
    _assert_trace(trace, "get_merchant_by_id")
    assert trace.input == {"id": "merch_jane_boutique_sg"}
    assert "Orchard" in trace.output_summary or result is not None


def test_find_transactions_by_merchant_category():
    # 5732 == Electronics Stores — Alex's high-risk trigger MCC.
    result, trace = _run_with_client(
        lambda cr: cr.find_transactions_by_merchant_category("cust_alex", "5732", limit=10)
    )
    _assert_trace(trace, "filter_merchant_by_category_code")
    assert trace.input["mcc_id"] == "5732"
    assert trace.input["customer_id"] == "cust_alex"
    assert result is not None


def test_search_similar_transactions():
    result, trace = _run_with_client(
        lambda cr: cr.search_similar_transactions("luxury Singapore", k=5)
    )
    _assert_trace(trace, "search_transaction_by_text")
    assert trace.input["query"] == "luxury Singapore"
    assert result is not None
