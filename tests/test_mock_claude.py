"""Tests for the Wave 8b ``MockClaudeClient``.

Confirms the canned per-hero traces give the expected verdicts and that
``score_stream`` emits a Claude-shaped event sequence (``thinking``,
``step``\\* with at least one ``llm`` step, ``final``) within the ~2s
budget. Also covers the chat divergence between IRIS and naive-RAG and
verifies ``deps._resolve_agent_mode`` lands on ``mock`` by default when
no Anthropic key is present.
"""

from __future__ import annotations

import asyncio

import pytest

from app.api import deps as api_deps
from app.mock_claude import MOCK_LLM_MODEL, MockClaudeClient
from app.schemas import TransactionPayload


HERO_VERDICTS = {
    "cust_mike": "approve",
    "cust_jane": "approve",
    "cust_alex": "block",
    "cust_sarah": "review",
}


@pytest.fixture
def mock_agent():
    return MockClaudeClient()


# ---------- per-hero verdicts --------------------------------------------

@pytest.mark.parametrize("customer_id,expected", list(HERO_VERDICTS.items()))
async def test_hero_verdicts(mock_agent, customer_id, expected):
    resp = await mock_agent.score(customer_id, TransactionPayload(amount=1, currency="USD"))
    assert resp.verdict == expected
    assert 0.0 <= resp.confidence <= 1.0
    assert resp.trace.llm_model == MOCK_LLM_MODEL
    assert resp.trace.steps, "every hero must record at least one step"
    # Analyst summary must follow the three-paragraph Reason/Policy/Action format.
    assert "**Reason**" in resp.reason
    assert "**Policy**" in resp.reason
    assert "**Action**" in resp.reason


async def test_unknown_customer_falls_back_to_mike(mock_agent):
    # Generic customers reuse Mike's canned plan (approve) — the mock never
    # crashes on an unknown id.
    resp = await mock_agent.score("cust_unknown", TransactionPayload(amount=1))
    assert resp.verdict == "approve"
    assert resp.trace.steps


# ---------- streaming shape ----------------------------------------------

async def _collect(agent, customer_id):
    events = []
    async for ev in agent.score_stream(customer_id, TransactionPayload(amount=1, currency="USD")):
        events.append(ev)
    return events


async def test_stream_emits_thinking_then_steps_then_final(mock_agent):
    events = await _collect(mock_agent, "cust_jane")
    types = [e["type"] for e in events]
    assert types[0] == "thinking"
    assert types[-1] == "final"
    assert "step" in types
    # There must be at least one LLM step and one tool step.
    llm_steps = [e for e in events if e["type"] == "step"
                 and e["step"].component == "llm"]
    tool_steps = [e for e in events if e["type"] == "step"
                  and e["step"].component != "llm"]
    assert llm_steps, "expected at least one llm step"
    assert tool_steps, "expected at least one tool step"


async def test_stream_step_components_match_schema(mock_agent):
    events = await _collect(mock_agent, "cust_alex")
    for ev in events:
        if ev["type"] != "step":
            continue
        step = ev["step"]
        assert step.component in (
            "context_retriever", "feature_store", "agent_memory",
            "policy_rag", "llm",
        )
        assert step.latency_ms >= 0
        assert step.output_summary


async def test_stream_score_matches_score_method(mock_agent):
    """score_stream's final event must equal what score() returns."""
    non_stream = await mock_agent.score(
        "cust_alex", TransactionPayload(amount=1240, currency="USD"),
    )
    events = await _collect(mock_agent, "cust_alex")
    final = next(e for e in events if e["type"] == "final")["response"]
    assert final.verdict == non_stream.verdict
    assert final.confidence == non_stream.confidence
    assert final.reason == non_stream.reason
    assert (
        [s.tool for s in final.trace.steps]
        == [s.tool for s in non_stream.trace.steps]
    )


async def test_stream_total_runtime_fits_demo_budget(mock_agent):
    """~2s total run is the demo brief; allow generous slack but require
    that the stream isn't instantaneous (the UI flicker depends on it)."""
    loop = asyncio.get_event_loop()
    t0 = loop.time()
    events = await _collect(mock_agent, "cust_sarah")
    elapsed = loop.time() - t0
    # The stream MUST take some real wall-time so the UI panels flicker.
    assert elapsed >= 0.8, f"stream finished too fast ({elapsed:.2f}s)"
    # And not so slow it drags the demo (Sarah has the most steps).
    assert elapsed <= 6.0, f"stream took too long ({elapsed:.2f}s)"
    assert events[-1]["type"] == "final"


# ---------- chat divergence ----------------------------------------------

async def test_chat_iris_vs_rag_diverges(mock_agent):
    iris = await mock_agent.chat_context_surface(
        "cust_jane", "Is Jane travelling right now?",
    )
    rag = await mock_agent.chat_naive_rag(
        "cust_jane", "Is Jane travelling right now?",
    )
    # IRIS must mention the customer / their context; RAG must not.
    assert "Jane" in iris.answer
    assert "Jane" not in rag.answer
    assert "Singapore" in iris.answer
    # RAG bot opens with the canonical phrase.
    assert rag.answer.startswith("Based on the bank's policy corpus")
    # Both produce a trace with at least one llm step.
    for resp in (iris, rag):
        assert resp.trace.llm_model == MOCK_LLM_MODEL
        assert any(s.component == "llm" for s in resp.trace.steps)


async def test_chat_naive_rag_has_only_policy_tools(mock_agent):
    rag = await mock_agent.chat_naive_rag("cust_jane", "What's the foreign-travel policy?")
    non_llm_tools = [s.tool for s in rag.trace.steps if s.component != "llm"]
    assert non_llm_tools == ["search_policy"], (
        f"naive-RAG must only call search_policy, got {non_llm_tools}"
    )


# ---------- deps mode resolution -----------------------------------------

def test_resolve_agent_mode_defaults_to_mock_without_key(monkeypatch):
    monkeypatch.delenv("AGENT_MODE", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert api_deps._resolve_agent_mode() == "mock"


def test_resolve_agent_mode_picks_claude_when_key_present(monkeypatch):
    monkeypatch.delenv("AGENT_MODE", raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-anything")
    assert api_deps._resolve_agent_mode() == "claude"


@pytest.mark.parametrize("mode", ["stub", "claude", "mock"])
def test_resolve_agent_mode_explicit_wins(monkeypatch, mode):
    monkeypatch.setenv("AGENT_MODE", mode)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert api_deps._resolve_agent_mode() == mode
