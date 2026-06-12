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


# Applied per-test rather than module-wide so the Wave 7k.1 parser
# edge-case tests at the bottom of this file still run in offline mode.
def _live_test(fn):
    fn = pytest.mark.live(fn)
    fn = pytest.mark.skipif(
        not all(os.environ.get(k) for k in _REQUIRED_ENV),
        reason=(
            "live Claude tests require ANTHROPIC_API_KEY and REDIS_URL; "
            "skipped in offline-rehearsal mode."
        ),
    )(fn)
    return fn


@pytest_asyncio.fixture(scope="module")
async def agent():
    """Build a ClaudeAgent on top of the same real backends the API uses."""
    from app.api import deps as api_deps
    from app.claude_agent import ClaudeAgent

    backends = await api_deps.get_backends()
    yield ClaudeAgent(backends)
    await api_deps.shutdown()


# ---------- hero-scenario verdicts ----------------------------------------

@_live_test
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


@_live_test
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


@_live_test
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

@_live_test
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


@_live_test
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


# ---------- Wave 7k.1: offline parser edge cases --------------------------
#
# These exercise ``_parse_verdict_payload`` directly so they run without
# Claude credentials. They cover the three failure modes the prompt drift
# could plausibly produce on Jane / Alex: raw newlines in the JSON string
# value, prose preamble before the JSON, prose afterthought after it.

from app.claude_agent import _parse_verdict_payload  # noqa: E402


def test_parser_handles_raw_newlines_inside_reason_string():
    """Claude occasionally emits literal newlines inside the multi-paragraph
    reason — the parser must escape and recover instead of degrading."""
    raw = (
        '{"verdict": "approve", "confidence": 0.88, "reason": "**Reason**\n'
        "Jane tapped her card in Singapore for S$1,820, explained by her "
        'declared travel.\n\n**Policy**\nVerified context overrides surface '
        'anomaly.\n\n**Action**\nApproved."}'
    )
    verdict, confidence, reason = _parse_verdict_payload(raw)
    assert verdict == "approve"
    assert confidence == 0.88
    assert "**Reason**" in reason and "**Policy**" in reason and "**Action**" in reason


def test_parser_handles_markdown_preamble_before_json():
    """A leading prose paragraph (or fenced thinking) must not block the
    parser from locating the real JSON object."""
    raw = (
        "Here is my final decision based on the evidence gathered:\n\n"
        '{"verdict":"block","confidence":0.96,"reason":"**Reason**\\n'
        'Alex card attempted $1,240 in Sao Paulo from an unseen device.\\n\\n'
        '**Policy**\\nStacked fraud indicators with no context = block.\\n\\n'
        '**Action**\\nBlocked and locked international use."}'
    )
    verdict, confidence, reason = _parse_verdict_payload(raw)
    assert verdict == "block"
    assert confidence == 0.96
    assert "Alex" in reason


def test_parser_handles_prose_afterthought_after_json():
    """A trailing prose paragraph must not confuse the parser into picking
    the wrong verdict — the real verdict JSON should still win."""
    raw = (
        '{"verdict":"approve","confidence":0.92,"reason":"**Reason**\\n'
        'Jane spend explained by travel.\\n\\n**Policy**\\nContext over '
        'anomaly.\\n\\n**Action**\\nApproved."}\n\n'
        "Note: I considered routing this to review but the travel memory "
        "made the decision clear."
    )
    verdict, confidence, reason = _parse_verdict_payload(raw)
    assert verdict == "approve"
    assert confidence == 0.92
    assert "Jane" in reason


def test_parser_regex_fallback_recovers_verdict_on_malformed_body():
    """If even the balanced-brace recovery fails, the regex fallback must
    still extract the verdict rather than silently degrading to review."""
    raw = (
        'After considering everything: "verdict": "block", "confidence": 0.91 '
        '— this one is clearly fraud and we should not let it through.'
    )
    verdict, confidence, reason = _parse_verdict_payload(raw)
    assert verdict == "block"
    assert confidence == 0.91
    assert reason
