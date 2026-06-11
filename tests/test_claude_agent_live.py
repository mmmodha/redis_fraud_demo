"""Live Wave 3b tests — real Claude tool-use loop against real Redis IRIS.

Marked ``@pytest.mark.live`` and auto-skipped when ``ANTHROPIC_API_KEY`` or
``REDIS_URL`` is unset, so unit-test runs on machines without credentials
remain green.

Run from inside the backend container:

    docker compose -f infra/docker-compose.yml exec backend \\
        pytest tests/test_claude_agent_live.py -v -m live
"""

from __future__ import annotations

import os

import pytest
import pytest_asyncio

from app.schemas import TransactionPayload


_REQUIRED_ENV = ("ANTHROPIC_API_KEY", "REDIS_URL")


pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(
        not all(os.environ.get(k) for k in _REQUIRED_ENV),
        reason=(
            "live Claude tests require ANTHROPIC_API_KEY and REDIS_URL; "
            "skipped in offline-rehearsal mode."
        ),
    ),
]


@pytest_asyncio.fixture(scope="module")
async def agent():
    """Build a ClaudeAgent on top of the same real backends the API uses."""
    from app.api import deps as api_deps
    from app.claude_agent import ClaudeAgent

    backends = await api_deps.get_backends()
    yield ClaudeAgent(backends)
    await api_deps.shutdown()


# ---------- hero-scenario verdicts ----------------------------------------

async def test_mike_clean_approves(agent):
    resp = await agent.score("cust_mike", TransactionPayload(
        amount=6.75, currency="USD",
        merchant_id="merch_mike_coffee", country="US",
        card_id="card_mike_visa",
    ))
    assert resp.verdict == "approve", f"got {resp.verdict}: {resp.reason}"
    assert resp.trace.llm_model.startswith("claude-"), resp.trace.llm_model
    assert any(s.component == "llm" for s in resp.trace.steps)
    assert any(s.component != "llm" for s in resp.trace.steps), (
        "agent should have called at least one IRIS tool"
    )
    # At least one LLM step must report a non-zero token count.
    llm_steps = [s for s in resp.trace.steps if s.component == "llm"]
    assert any((s.output_data or {}).get("input_tokens", 0) > 0 for s in llm_steps)


async def test_jane_travel_approves(agent):
    resp = await agent.score("cust_jane", TransactionPayload(
        amount=480, currency="SGD",
        merchant_id="merch_jane_boutique_sg", country="SG",
        card_id="card_jane_visa",
    ))
    assert resp.verdict == "approve", f"got {resp.verdict}: {resp.reason}"
    tools = {s.tool for s in resp.trace.steps}
    # Memory must have been consulted for Jane's travel window.
    assert "get_customer_memory" in tools


async def test_alex_fraud_blocks(agent):
    resp = await agent.score("cust_alex", TransactionPayload(
        amount=2400, currency="USD",
        merchant_id="merch_alex_electronics_br", country="BR",
        device_id="dev_alex_unknown_android",
        card_id="card_alex_visa",
    ))
    assert resp.verdict == "block", f"got {resp.verdict}: {resp.reason}"
    components = {s.component for s in resp.trace.steps}
    # The block decision must have consulted at least two of: memory,
    # recent transactions, device history (per the fraud_agent prompt).
    expected_signals = {"agent_memory", "context_retriever", "feature_store"}
    assert len(components & expected_signals) >= 2


# ---------- chatbot side-by-side ------------------------------------------

async def test_chat_context_surface_mentions_jane_singapore(agent):
    resp = await agent.chat_context_surface(
        customer_id="cust_jane",
        message="any upcoming travel?",
    )
    assert "Singapore" in resp.answer, (
        f"context-surface should surface Jane's declared travel; "
        f"got: {resp.answer!r}"
    )
    tools = {s.tool for s in resp.trace.steps}
    assert "get_customer_memory" in tools


async def test_chat_naive_rag_does_not_mention_jane_singapore(agent):
    resp = await agent.chat_naive_rag(
        customer_id="cust_jane",
        message="any upcoming travel?",
    )
    assert "Singapore" not in resp.answer, (
        f"naive-rag must not leak Jane-specific data; got: {resp.answer!r}"
    )
    # Only search_policy may be used by the naive bot.
    tool_steps = [s for s in resp.trace.steps if s.component != "llm"]
    assert all(s.tool == "search_policy" for s in tool_steps), (
        f"naive-rag called non-policy tools: "
        f"{[s.tool for s in tool_steps]}"
    )
