"""Canned-trace replacement for :class:`app.claude_agent.ClaudeAgent`.

Wired in by :mod:`app.api.deps` when no ``ANTHROPIC_API_KEY`` is configured
so the trace UI still flickers as if Claude were thinking — every
right-rail panel, the timeline strip, and the analyst summary populate
from per-hero canned data with small artificial delays. No Anthropic
network call, no IRIS tool dispatch. Total mock run is ~2s.

Public surface matches :class:`ClaudeAgent` / :class:`StubAgent` so
:func:`app.api.deps.get_agent` can hand any of the three to FastAPI.
"""

from __future__ import annotations

import asyncio
import random
import time
from typing import Any, AsyncIterator, Optional

from app.agent_tools import Backends
from app.schemas import (
    AgentTrace,
    ChatMessage,
    ChatResponse,
    ScoreResponse,
    TraceStep,
    TransactionPayload,
)


MOCK_LLM_MODEL = "claude-sonnet-4-5-mock"

# Per-step delay envelope so the UI ticks one event at a time.
_STEP_DELAY_MIN = 0.15
_STEP_DELAY_MAX = 0.40
# Initial "LLM is thinking" pause before any tool runs.
_INITIAL_THINK_MIN = 0.30
_INITIAL_THINK_MAX = 0.55


# ---------- canned per-hero data -----------------------------------------

# Each plan is a list of TraceStep "templates" — every entry becomes one
# ``step`` event with the listed fields. ``latency_ms`` is filled in at
# emit time with a small jitter so successive runs aren't byte-identical.

_MIKE_PLAN: list[dict[str, Any]] = [
    {"component": "context_retriever", "tool": "get_customer_context",
     "input": {"customer_id": "cust_mike"},
     "summary": "Mike (US-Austin), card_mike_visa, account 4y",
     "data": {"customer_id": "cust_mike", "name": "Mike",
              "home_country": "US", "home_city": "Austin",
              "primary_card_id": "card_mike_visa"},
     "keys": ["customer:cust_mike"]},
    {"component": "feature_store", "tool": "get_velocity_features",
     "input": {"card_id": "card_mike_visa"},
     "summary": "v1h=0 v24h=2 v7d=10 avg30d=12.50",
     "data": {"velocity_1h": 0, "velocity_24h": 2, "velocity_7d": 10,
              "amount_avg_30d": 12.5, "amount_max_24h": 40.0,
              "geo_entropy": 0.05, "new_device_24h": 0},
     "keys": ["feat:card_mike_visa"]},
    {"component": "policy_rag", "tool": "search_policy",
     "input": {"query": "low-risk approval established merchant", "k": 5},
     "summary": "3 chunk(s) — Approval Thresholds, Established Merchants, Velocity",
     "data": {"chunks": [
         {"chunk_id": "p-001", "doc_id": "policy", "title": "Approval Thresholds",
          "text": "Transactions inside a customer's historical spend pattern auto-approve in real time."},
         {"chunk_id": "p-007", "doc_id": "policy", "title": "Established Merchants",
          "text": "Repeat merchants on the customer's card history bypass the new-merchant friction lane."},
     ]},
     "keys": ["idx:policies"]},
]

_JANE_PLAN: list[dict[str, Any]] = [
    {"component": "context_retriever", "tool": "get_customer_context",
     "input": {"customer_id": "cust_jane"},
     "summary": "Jane (US-SF), card_jane_visa, account 6y",
     "data": {"customer_id": "cust_jane", "name": "Jane",
              "home_country": "US", "home_city": "San Francisco",
              "primary_card_id": "card_jane_visa"},
     "keys": ["customer:cust_jane"]},
    {"component": "context_retriever", "tool": "get_recent_transactions",
     "input": {"customer_id": "cust_jane", "days": 30, "limit": 25},
     "summary": "8 record(s) — airline + hotel last week, coffee in SG yesterday",
     "data": {"items": [
         {"merchant_name": "Singapore Airlines", "amount": 1840, "currency": "USD",
          "country": "US", "ts": "2099-11-08"},
         {"merchant_name": "Marina Bay Hotel", "amount": 420, "currency": "SGD",
          "country": "SG", "ts": "2099-11-11"},
     ], "count": 8},
     "keys": []},
    {"component": "agent_memory", "tool": "get_customer_memory",
     "input": {"customer_id": "cust_jane"},
     "summary": "declared travel SG 2099-11-10 → 2099-11-17",
     "data": {"customer_id": "cust_jane",
              "travel_windows": [{"start_date": "2099-11-10",
                                  "end_date": "2099-11-17",
                                  "destinations": ["Singapore"],
                                  "source": "customer-app"}],
              "prior_disputes": [], "flagged_devices": []},
     "keys": ["mem:cust_jane"]},
    {"component": "context_retriever", "tool": "get_merchant_reputation",
     "input": {"merchant_id": "merch_jane_boutique_sg"},
     "summary": "trusted luxury boutique, SG, 4.8/5 reputation",
     "data": {"merchant_id": "merch_jane_boutique_sg",
              "name": "Orchard Luxury", "country": "SG",
              "category": "luxury goods", "reputation": "trusted"},
     "keys": ["merchant:merch_jane_boutique_sg"]},
    {"component": "policy_rag", "tool": "search_policy",
     "input": {"query": "cross-border travel exception declared travel window", "k": 5},
     "summary": "3 chunk(s) — Foreign Travel, Velocity Tolerance, Declared Trips",
     "data": {"chunks": [
         {"chunk_id": "p-014", "doc_id": "policy", "title": "Foreign Travel",
          "text": "A declared travel window widens velocity tolerance for the destination country."},
     ]},
     "keys": ["idx:policies"]},
]

_ALEX_PLAN: list[dict[str, Any]] = [
    {"component": "context_retriever", "tool": "get_customer_context",
     "input": {"customer_id": "cust_alex"},
     "summary": "Alex (US-SF), card_alex_visa, account 5y, no intl history",
     "data": {"customer_id": "cust_alex", "name": "Alex",
              "home_country": "US", "home_city": "San Francisco",
              "primary_card_id": "card_alex_visa"},
     "keys": ["customer:cust_alex"]},
    {"component": "context_retriever", "tool": "get_devices_for_customer",
     "input": {"customer_id": "cust_alex", "limit": 25},
     "summary": "1 known device — MacBook (US), last seen this morning",
     "data": {"items": [
         {"device_id": "dev_alex_macbook", "os": "macOS", "country": "US",
          "first_seen": "2021-03-12", "last_seen": "2099-12-05T08:14:00Z"},
     ], "count": 1},
     "keys": []},
    {"component": "feature_store", "tool": "get_new_device_flag",
     "input": {"customer_id": "cust_alex", "device_id": "dev_alex_unknown_android"},
     "summary": "device first-seen=true (never seen on this card)",
     "data": {"device_known_to_card": False, "new_device_24h": True,
              "first_seen": None},
     "keys": ["feat:_dev:card_alex_visa"]},
    {"component": "feature_store", "tool": "get_geo_entropy",
     "input": {"customer_id": "cust_alex"},
     "summary": "entropy=0.91 (impossible-travel band)",
     "data": {"geo_entropy": 0.91, "window_days": 7},
     "keys": ["feat:card_alex_visa"]},
    {"component": "context_retriever", "tool": "find_similar_fraud",
     "input": {"query": "new-device high-value electronics foreign card-not-present", "k": 5},
     "summary": "5 record(s) — known fraud cluster: BR electronics CNP",
     "data": {"items": [
         {"transaction_id": "tx_known_fraud_42", "merchant_name": "Sao Paulo Eletro",
          "amount": 1190, "country": "BR", "outcome": "chargeback"},
     ], "count": 5},
     "keys": []},
    {"component": "policy_rag", "tool": "search_policy",
     "input": {"query": "new-device high-value block step-up auth", "k": 5},
     "summary": "3 chunk(s) — New Device, Impossible Travel, Block Rules",
     "data": {"chunks": [
         {"chunk_id": "p-021", "doc_id": "policy", "title": "Impossible Travel",
          "text": "Multiple high-confidence fraud indicators with no offsetting context → block immediately."},
     ]},
     "keys": ["idx:policies"]},
]

_SARAH_PLAN: list[dict[str, Any]] = [
    {"component": "context_retriever", "tool": "get_customer_context",
     "input": {"customer_id": "cust_sarah"},
     "summary": "Sarah (US-SF), card_sarah_visa, account 18mo, p95 spend $280",
     "data": {"customer_id": "cust_sarah", "name": "Sarah",
              "home_country": "US", "home_city": "San Francisco",
              "primary_card_id": "card_sarah_visa"},
     "keys": ["customer:cust_sarah"]},
    {"component": "context_retriever", "tool": "get_recent_transactions",
     "input": {"customer_id": "cust_sarah", "days": 7, "limit": 25},
     "summary": "6 record(s) — JFK arrival 2d ago, Manhattan coffee this morning",
     "data": {"items": [
         {"merchant_name": "JFK Taxi", "amount": 78, "country": "US",
          "ts": "2099-12-03"},
         {"merchant_name": "Joe Coffee", "amount": 6.5, "country": "US",
          "ts": "2099-12-05T09:12:00Z"},
     ], "count": 6},
     "keys": []},
    {"component": "agent_memory", "tool": "get_customer_memory",
     "input": {"customer_id": "cust_sarah"},
     "summary": "declared NYC trip 2099-12-03 → 2099-12-08; known iPhone",
     "data": {"customer_id": "cust_sarah",
              "travel_windows": [{"start_date": "2099-12-03",
                                  "end_date": "2099-12-08",
                                  "destinations": ["New York"],
                                  "source": "customer-app"}]},
     "keys": ["mem:cust_sarah"]},
    {"component": "context_retriever", "tool": "get_pending_review",
     "input": {"customer_id": "cust_sarah"},
     "summary": "pending 1450 USD at Tiffany & Co (US)",
     "data": {"transaction_id": "tx_sarah_tiffany", "amount": 1450,
              "currency": "USD", "merchant_name": "Tiffany & Co",
              "merchant_country": "US", "merchant_category": "jewelry",
              "foreign_country": False, "device_first_seen_today": False,
              "impossible_travel": False},
     "keys": ["pending_review:cust_sarah"]},
    {"component": "feature_store", "tool": "get_velocity_features",
     "input": {"card_id": "card_sarah_visa"},
     "summary": "v1h=1 v24h=3 v7d=12 avg30d=68.40 max24h=180.00",
     "data": {"velocity_1h": 1, "velocity_24h": 3, "velocity_7d": 12,
              "amount_avg_30d": 68.40, "amount_max_24h": 180.0,
              "geo_entropy": 0.30, "new_device_24h": 0},
     "keys": ["feat:card_sarah_visa"]},
    {"component": "policy_rag", "tool": "search_policy",
     "input": {"query": "step-up authentication travel-confirmed high-value novel merchant category", "k": 5},
     "summary": "3 chunk(s) — Step-Up Auth, Novel MCC, Confirmed Travel",
     "data": {"chunks": [
         {"chunk_id": "p-033", "doc_id": "policy", "title": "Step-Up Authentication",
          "text": "Verified context + atypical spend → route to step-up rather than block or auto-approve."},
     ]},
     "keys": ["idx:policies"]},
]


# Analyst summaries lifted verbatim from prompts/fraud_agent.md worked
# examples so mock-mode output matches presenter-mode tone exactly.
_HERO_PLANS: dict[str, dict[str, Any]] = {
    "cust_mike": {
        "verdict": "approve", "confidence": 0.95, "plan": _MIKE_PLAN,
        "reason": (
            "**Reason**\n"
            "Mike tapped his card at Radio Coffee in Austin for $6.75. "
            "It's a local merchant he's bought from before, on his known "
            "device, well within his usual spend pattern. No anomaly "
            "anywhere — this is exactly the kind of transaction we see "
            "from him every week.\n\n"
            "**Policy**\n"
            "When every signal aligns with the customer's established "
            "pattern, we auto-approve in real-time without involving a "
            "human reviewer.\n\n"
            "**Action**\n"
            "We approved the $6.75 charge in 187 milliseconds. "
            "No friction for Mike, no analyst time spent."
        ),
    },
    "cust_jane": {
        "verdict": "approve", "confidence": 0.88, "plan": _JANE_PLAN,
        "reason": (
            "**Reason**\n"
            "Jane's card was tapped at a luxury boutique in Singapore for "
            "S$1,820 — a high-value international purchase that would look "
            "suspicious in isolation. But we checked her recent activity "
            "and found she booked a flight to Singapore last week and "
            "checked into her hotel yesterday. Her travel context fully "
            "explains the location and the spend level.\n\n"
            "**Policy**\n"
            "When a surface-level anomaly is explained by verified "
            "context, we approve confidently rather than declining and "
            "frustrating a legitimate customer.\n\n"
            "**Action**\n"
            "We approved the S$1,820 charge. Jane never knows we even "
            "paused to check."
        ),
    },
    "cust_alex": {
        "verdict": "block", "confidence": 0.96, "plan": _ALEX_PLAN,
        "reason": (
            "**Reason**\n"
            "Alex's card just attempted $1,240 at an electronics merchant "
            "in São Paulo, Brazil — from a device we've never seen "
            "before. Alex has no international transactions on this card "
            "in five years, his known device is currently in San "
            "Francisco, and the velocity is physically impossible. "
            "Multiple independent fraud indicators all point the same "
            "direction.\n\n"
            "**Policy**\n"
            "When several high-confidence fraud indicators stack and no "
            "verified context explains them, we block immediately to "
            "prevent loss.\n\n"
            "**Action**\n"
            "We blocked the $1,240 attempt and locked the card from "
            "international use. Alex will get a confirmation prompt to "
            "verify whether this was him."
        ),
    },
    "cust_sarah": {
        "verdict": "review", "confidence": 0.86, "plan": _SARAH_PLAN,
        "reason": (
            "**Reason**\n"
            "Sarah's card was tapped at Tiffany & Co in Manhattan for "
            "$1,450. We confirmed she's genuinely there — her flight to "
            "JFK landed two days ago, she's at a hotel nearby, and she "
            "bought coffee in Manhattan this morning. But $1,450 is "
            "roughly five times her typical spend, and she's never "
            "bought jewelry on this card before. Real travel, but an "
            "unusual purchase.\n\n"
            "**Policy**\n"
            "When verified context rules out fraud but the spend pattern "
            "is materially outside the customer's norm, we route to "
            "step-up authentication rather than blocking or "
            "auto-approving — one extra signal lets us be confident "
            "either way.\n\n"
            "**Action**\n"
            "We sent Sarah a one-tap confirmation push to her phone. She "
            "confirmed, so we approved the $1,450 charge. If she hadn't, "
            "we'd have blocked it."
        ),
    },
}


# ---------- chat divergence (RAG vs IRIS) --------------------------------

_CHAT_POLICY_STEP = {
    "component": "policy_rag", "tool": "search_policy",
    "input": {"query": "foreign travel velocity tolerance step-up", "k": 3},
    "summary": "3 chunk(s) — Foreign Travel, Step-Up Auth",
    "data": {"chunks": [
        {"chunk_id": "p-014", "doc_id": "policy", "title": "Foreign Travel",
         "text": "A declared travel window widens velocity tolerance for the destination country."},
        {"chunk_id": "p-033", "doc_id": "policy", "title": "Step-Up Authentication",
         "text": "Verified context + atypical spend → route to step-up rather than block."},
    ]},
    "keys": ["idx:policies"],
}


def _iris_chat_plan(customer_id: str) -> tuple[list[dict[str, Any]], str]:
    """Tool sequence + canned answer for ``/chat/context-surface``.

    Returns a steps list (TraceStep templates) and the analyst-tone answer
    so the side-by-side panel reads on-message even without live tools.
    """
    plan = _HERO_PLANS.get(customer_id)
    if plan is None:
        # Generic narrative — still divergent from RAG (mentions the customer
        # id, real RAG bot would not).
        steps = [
            {"component": "context_retriever", "tool": "get_customer_context",
             "input": {"customer_id": customer_id},
             "summary": f"profile for {customer_id}",
             "data": {"customer_id": customer_id}, "keys": [f"customer:{customer_id}"]},
            _CHAT_POLICY_STEP,
        ]
        answer = (
            f"For {customer_id}: I correlated their profile with the bank's "
            "policy corpus. Nothing unusual is flagged in Agent Memory; "
            "standard travel and velocity policy applies."
        )
        return steps, answer

    # Pick one customer-shaped tool sequence: memory + recent + policy.
    name = customer_id.replace("cust_", "").capitalize()
    if customer_id == "cust_jane":
        narrative = (
            f"{name} has a declared travel window to Singapore in Agent "
            "Memory (2099-11-10 → 2099-11-17) and recent activity shows a "
            "Singapore Airlines booking and a Marina Bay Hotel charge. "
            "Her cross-border spend is fully explained by that context."
        )
    elif customer_id == "cust_mike":
        narrative = (
            f"{name}'s recent activity is small repeat purchases at "
            "established merchants in Austin. No travel windows on file, "
            "no flagged devices, velocity well inside his usual envelope."
        )
    elif customer_id == "cust_alex":
        narrative = (
            f"{name} has no international transactions on file for the last "
            "five years and his known device is currently in San Francisco. "
            "Any foreign card-not-present attempt is therefore highly "
            "anomalous against his memory and device history."
        )
    elif customer_id == "cust_sarah":
        narrative = (
            f"{name} declared an NYC trip (Dec 3–8) and we can see her at "
            "JFK two days ago and a Manhattan coffee this morning. Her "
            "typical spend on this card is ~$280; any $1k+ charge is "
            "materially atypical and warrants step-up auth."
        )
    else:
        narrative = f"Recent activity for {name} is consistent with profile."
    answer = (
        f"{narrative} Policy reference: a declared travel window widens "
        "velocity tolerance for the destination country; verified context "
        "plus atypical spend routes to step-up authentication."
    )

    steps = [
        {"component": "agent_memory", "tool": "get_customer_memory",
         "input": {"customer_id": customer_id},
         "summary": f"memory for {customer_id}",
         "data": {"customer_id": customer_id}, "keys": [f"mem:{customer_id}"]},
        {"component": "context_retriever", "tool": "get_recent_transactions",
         "input": {"customer_id": customer_id, "days": 7, "limit": 25},
         "summary": "recent activity window",
         "data": {"items": [], "count": 0}, "keys": []},
        _CHAT_POLICY_STEP,
    ]
    return steps, answer


def _rag_chat_answer() -> str:
    return (
        "Based on the bank's policy corpus: a declared travel window "
        "widens velocity tolerance for the destination country, and "
        "verified-context-plus-atypical-spend routes the transaction to "
        "step-up authentication rather than an outright block."
    )


# ---------- helpers ------------------------------------------------------

def _llm_step(round_num: int, num_tools: int, stop_reason: str,
              in_tokens: int, out_tokens: int, latency_ms: int) -> TraceStep:
    return TraceStep(
        component="llm",
        tool="anthropic.messages.create",
        input={"model": MOCK_LLM_MODEL, "num_tools": num_tools, "round": round_num},
        output_summary=f"stop={stop_reason} in_tokens={in_tokens} out_tokens={out_tokens}",
        output_data={"stop_reason": stop_reason,
                     "input_tokens": in_tokens, "output_tokens": out_tokens},
        latency_ms=latency_ms,
        redis_keys_touched=[],
    )


def _tool_step(template: dict[str, Any], latency_ms: int) -> TraceStep:
    return TraceStep(
        component=template["component"],
        tool=template["tool"],
        input=dict(template["input"]),
        output_summary=template["summary"],
        output_data=template["data"],
        latency_ms=latency_ms,
        redis_keys_touched=list(template.get("keys") or []),
    )


# ---------- mock client --------------------------------------------------

class MockClaudeClient:
    """Drop-in stand-in for :class:`ClaudeAgent` with canned per-hero traces.

    Same public coroutines as ``ClaudeAgent`` / ``StubAgent``. ``backends``
    is accepted for signature parity but never used — the mock never calls
    any tool dispatcher.
    """

    def __init__(self, backends: Optional[Backends] = None) -> None:
        # backends is intentionally unused but kept for parity.
        self._backends = backends
        self._model = MOCK_LLM_MODEL

    # --- /agent/score -----------------------------------------------------

    async def score(
        self,
        customer_id: str,
        transaction: Optional[TransactionPayload],
    ) -> ScoreResponse:
        final: Optional[ScoreResponse] = None
        async for event in self.score_stream(customer_id, transaction):
            if event["type"] == "final":
                final = event["response"]
        assert final is not None, "score_stream must yield a final event"
        return final

    async def score_stream(
        self,
        customer_id: str,
        transaction: Optional[TransactionPayload],
    ) -> AsyncIterator[dict[str, Any]]:
        plan = _HERO_PLANS.get(customer_id) or _HERO_PLANS["cust_mike"]
        tool_templates: list[dict[str, Any]] = plan["plan"]
        rng = random.Random(customer_id)
        steps: list[TraceStep] = []
        t0 = time.perf_counter()

        # Round 1: thinking → LLM (decides to call tools).
        yield {"type": "thinking", "round": 1}
        await asyncio.sleep(_INITIAL_THINK_MIN
                            + rng.random() * (_INITIAL_THINK_MAX - _INITIAL_THINK_MIN))
        llm1 = _llm_step(
            round_num=1, num_tools=len(tool_templates),
            stop_reason="tool_use", in_tokens=1820, out_tokens=240,
            latency_ms=320 + int(rng.random() * 80),
        )
        steps.append(llm1)
        yield {"type": "step", "step": llm1}
        await asyncio.sleep(_STEP_DELAY_MIN
                            + rng.random() * (_STEP_DELAY_MAX - _STEP_DELAY_MIN))

        # Each tool call as a step event.
        for tmpl in tool_templates:
            step = _tool_step(tmpl, latency_ms=4 + int(rng.random() * 30))
            steps.append(step)
            yield {"type": "step", "step": step}
            await asyncio.sleep(_STEP_DELAY_MIN
                                + rng.random() * (_STEP_DELAY_MAX - _STEP_DELAY_MIN))

        # Round 2: thinking → LLM (returns final verdict text).
        yield {"type": "thinking", "round": 2}
        await asyncio.sleep(_INITIAL_THINK_MIN
                            + rng.random() * (_INITIAL_THINK_MAX - _INITIAL_THINK_MIN))
        llm2 = _llm_step(
            round_num=2, num_tools=len(tool_templates),
            stop_reason="end_turn", in_tokens=2480, out_tokens=320,
            latency_ms=380 + int(rng.random() * 80),
        )
        steps.append(llm2)
        yield {"type": "step", "step": llm2}

        total = int((time.perf_counter() - t0) * 1000)
        yield {
            "type": "final",
            "response": ScoreResponse(
                verdict=plan["verdict"],
                confidence=plan["confidence"],
                reason=plan["reason"],
                trace=AgentTrace(steps=steps, total_latency_ms=total,
                                 llm_model=self._model),
            ),
        }

    # --- /chat/context-surface --------------------------------------------

    async def chat_context_surface(
        self, customer_id: str, message: str,
        history: Optional[list[ChatMessage]] = None,
    ) -> ChatResponse:
        templates, answer = _iris_chat_plan(customer_id)
        return await self._chat_emit(templates, answer)

    # --- /chat/naive-rag --------------------------------------------------

    async def chat_naive_rag(
        self, customer_id: str, message: str,
        history: Optional[list[ChatMessage]] = None,
    ) -> ChatResponse:
        # Naive RAG is policy-only; customer_id is ignored on purpose so the
        # side-by-side panel shows divergence: no customer-specific data.
        templates = [_CHAT_POLICY_STEP]
        return await self._chat_emit(templates, _rag_chat_answer())

    async def _chat_emit(
        self, templates: list[dict[str, Any]], answer: str,
    ) -> ChatResponse:
        rng = random.Random(answer)
        steps: list[TraceStep] = []
        t0 = time.perf_counter()

        # Single up-front LLM step — chat endpoints don't stream.
        steps.append(_llm_step(
            round_num=1, num_tools=len(templates), stop_reason="tool_use",
            in_tokens=620, out_tokens=140,
            latency_ms=240 + int(rng.random() * 60),
        ))
        for tmpl in templates:
            steps.append(_tool_step(tmpl, latency_ms=3 + int(rng.random() * 20)))
        steps.append(_llm_step(
            round_num=2, num_tools=len(templates), stop_reason="end_turn",
            in_tokens=820, out_tokens=180,
            latency_ms=300 + int(rng.random() * 60),
        ))

        total = int((time.perf_counter() - t0) * 1000)
        return ChatResponse(
            answer=answer,
            trace=AgentTrace(steps=steps, total_latency_ms=total,
                             llm_model=self._model),
        )


__all__ = ["MockClaudeClient", "MOCK_LLM_MODEL"]
