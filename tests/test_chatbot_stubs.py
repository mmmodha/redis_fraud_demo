"""Tests for the two chatbot stubs.

The context-surface bot must include customer-specific data in its answer
(quoted from the actual returned tool payload); the naive-RAG bot must
answer the same question with only generic policy text and no customer data.
"""

from __future__ import annotations

import fakeredis
import pytest

from app.agent_tools import Backends
from app.stub_agent import StubAgent

from tests.test_stub_agent import FakeContextRetriever, FakePolicyRAG


@pytest.fixture
def redis_client():
    client = fakeredis.FakeRedis(decode_responses=True)
    client.json().set("mem:cust_jane", "$", {
        "customer_id": "cust_jane",
        "travel_windows": [
            {"start_date": "2099-11-10", "end_date": "2099-11-17",
             "destinations": ["Singapore"], "source": "seed"},
        ],
        "prior_disputes": [], "flagged_devices": [], "conversation_notes": [],
        "last_updated_at": "2026-06-11T00:00:00Z",
    })
    return client


@pytest.fixture
def agent(redis_client):
    return StubAgent(Backends(
        redis_client=redis_client,
        ctx=FakeContextRetriever(),
        policy_rag=FakePolicyRAG(),
    ))


# ---------- context-surface --------------------------------------------------

async def test_context_surface_travel_question_quotes_memory(agent):
    resp = await agent.chat_context_surface(
        customer_id="cust_jane",
        message="any upcoming travel?",
    )
    assert "Singapore" in resp.answer
    assert "2099-11-10" in resp.answer
    assert "2099-11-17" in resp.answer
    tools = [s.tool for s in resp.trace.steps]
    assert "search_policy" in tools
    assert "get_customer_memory" in tools


async def test_context_surface_recent_transactions_quotes_data(agent):
    resp = await agent.chat_context_surface(
        customer_id="cust_jane",
        message="show me her recent transactions",
    )
    tools = [s.tool for s in resp.trace.steps]
    assert "get_recent_transactions" in tools
    # The fake context retriever echoes the tool name into its payload,
    # which the stub answer is expected to quote.
    assert "filter_transaction_by_customer_id" in resp.answer


async def test_context_surface_falls_back_to_customer_context(agent):
    resp = await agent.chat_context_surface(
        customer_id="cust_jane",
        message="give me a general summary",
    )
    tools = [s.tool for s in resp.trace.steps]
    assert "get_customer_context" in tools


# ---------- naive-rag --------------------------------------------------------

async def test_naive_rag_returns_generic_policy_text(agent):
    resp = await agent.chat_naive_rag(
        customer_id="cust_jane",
        message="any upcoming travel?",
    )
    tools = [s.tool for s in resp.trace.steps]
    components = [s.component for s in resp.trace.steps]
    # ONLY the policy index is consulted.
    assert tools == ["search_policy"]
    assert components == ["policy_rag"]
    # No customer-specific data leaks into the answer.
    assert "Singapore" not in resp.answer
    assert "cust_jane" not in resp.answer
    assert "Based on the bank's policy corpus" in resp.answer


async def test_naive_rag_and_context_surface_diverge_on_same_question(agent):
    question = "any upcoming travel?"
    iris = await agent.chat_context_surface("cust_jane", question)
    rag = await agent.chat_naive_rag("cust_jane", question)
    # Same input → demonstrably different output: IRIS sees Singapore, RAG doesn't.
    assert "Singapore" in iris.answer
    assert "Singapore" not in rag.answer
    # The traces differ in component coverage too.
    iris_components = {s.component for s in iris.trace.steps}
    rag_components = {s.component for s in rag.trace.steps}
    assert "agent_memory" in iris_components
    assert "agent_memory" not in rag_components
