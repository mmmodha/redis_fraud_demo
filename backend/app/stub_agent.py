"""Deterministic stand-in for the (Wave 3b) Claude fraud agent.

Implements the same shape Wave 3b will: a fraud-scoring entry point and two
chatbot entry points (context-surface and naive-RAG). The bot's *final*
verdict and templated answer are hard-coded per hero customer, but the calls
to the IRIS components are real — every TraceStep on the returned
``AgentTrace`` records an actual tool invocation against the real backends.

This lets Wave 4 (frontend) build the UI today against real shapes and real
side-panel data, and lets Wave 3b later drop in a Claude tool-use loop
without touching the stub's public interface.
"""

from __future__ import annotations

import asyncio
import random
import time
from typing import Any, AsyncIterator, Optional

from app.agent_tools import Backends, call_tool
from app.schemas import (
    AgentTrace,
    ChatMessage,
    ChatResponse,
    ScoreResponse,
    TraceStep,
    TransactionPayload,
)


LLM_MODEL = "stub-deterministic"


# ---------- shared helpers ------------------------------------------------

def _empty_trace_now() -> tuple[list[TraceStep], float]:
    return [], time.perf_counter()


def _finalise(steps: list[TraceStep], started: float) -> AgentTrace:
    total = int((time.perf_counter() - started) * 1000)
    return AgentTrace(steps=steps, total_latency_ms=total, llm_model=LLM_MODEL)


async def _call(
    backends: Backends, steps: list[TraceStep],
    name: str, args: dict[str, Any],
) -> Any:
    """Invoke a tool, append the trace step, return the payload."""
    out, step = await call_tool(name, args, backends=backends)
    steps.append(step)
    return out


def _first_text_field(payload: Any, key: str = "text", default: str = "") -> str:
    """Extract a text field from a Context Retriever result (which is wrapped
    in MCP-style ``{"content": [{"text": "..."}]}`` blobs) or a plain dict."""
    if isinstance(payload, dict):
        content = payload.get("content")
        if isinstance(content, list) and content:
            first = content[0]
            if isinstance(first, dict) and isinstance(first.get(key), str):
                return first[key]
        if isinstance(payload.get(key), str):
            return payload[key]
    if isinstance(payload, list) and payload:
        return _first_text_field(payload[0], key=key, default=default)
    return default


def _chunk_snippet(chunks: list[dict], limit: int = 300) -> str:
    if not chunks:
        return "(no policy match found)"
    text = chunks[0].get("text", "")
    title = chunks[0].get("title", "")
    body = text.strip().splitlines()
    first_para = " ".join(body[:4]).strip()
    snippet = first_para[: limit - 1] + "…" if len(first_para) > limit else first_para
    return f"[{title}] {snippet}" if title else snippet


# ---------- fraud scoring -------------------------------------------------

class StubAgent:
    """Deterministic fraud-scoring + chatbot stub.

    All methods take a ``Backends`` so the same instance can be reused across
    requests; the backends carry the live Redis client, Context Retriever, and
    PolicyRAG. Tests pass fakes for the same protocol."""

    def __init__(self, backends: Backends) -> None:
        self._backends = backends

    # --- /agent/score -----------------------------------------------------

    async def score(
        self,
        customer_id: str,
        transaction: Optional[TransactionPayload],
    ) -> ScoreResponse:
        if customer_id == "cust_mike":
            return await self._score_mike(transaction)
        if customer_id == "cust_jane":
            return await self._score_jane(transaction)
        if customer_id == "cust_alex":
            return await self._score_alex(transaction)
        if customer_id == "cust_sarah":
            return await self._score_sarah(transaction)
        return await self._score_generic(customer_id, transaction)

    async def score_stream(
        self,
        customer_id: str,
        transaction: Optional[TransactionPayload],
    ) -> AsyncIterator[dict[str, Any]]:
        """Same final verdict as :meth:`score` but yielded as a presenter-paced
        stream so the demo's trace strip and right-rail panels populate one
        step at a time even without a real Claude key.

        Event shapes match the contract used by :class:`ClaudeAgent`:
          ``{"type":"thinking","round":N}``
          ``{"type":"step","step":TraceStep}``
          ``{"type":"final","response":ScoreResponse}``
        """
        result = await self.score(customer_id, transaction)
        steps = list(result.trace.steps)
        rng = random.Random(customer_id)

        # Single synthesised "LLM thinking" pause up front — the stub has no
        # real multi-round LLM loop, so one beat is enough to fill the gap
        # between Run and the first tool step.
        t0 = time.perf_counter()
        yield {"type": "thinking", "round": 1}
        await asyncio.sleep(1.0 + rng.random() * 0.5)

        for step in steps:
            yield {"type": "step", "step": step}
            await asyncio.sleep(0.2 + rng.random() * 0.6)

        final_trace = AgentTrace(
            steps=steps,
            total_latency_ms=int((time.perf_counter() - t0) * 1000),
            llm_model=result.trace.llm_model,
        )
        yield {
            "type": "final",
            "response": ScoreResponse(
                verdict=result.verdict,
                confidence=result.confidence,
                reason=result.reason,
                trace=final_trace,
            ),
        }

    async def _score_mike(self, tx: Optional[TransactionPayload]) -> ScoreResponse:
        steps, t0 = _empty_trace_now()
        b = self._backends
        await _call(b, steps, "get_customer_context", {"customer_id": "cust_mike"})
        await _call(b, steps, "get_velocity_features", {"card_id": "card_mike_visa"})
        await _call(b, steps, "search_policy", {"query": "low-risk approval established merchant", "k": 5})
        return ScoreResponse(
            verdict="approve", confidence=0.92,
            reason="Velocity normal, established merchant, low-risk MCC.",
            trace=_finalise(steps, t0),
        )

    async def _score_jane(self, tx: Optional[TransactionPayload]) -> ScoreResponse:
        steps, t0 = _empty_trace_now()
        b = self._backends
        await _call(b, steps, "get_customer_context", {"customer_id": "cust_jane"})
        await _call(b, steps, "get_recent_transactions", {"customer_id": "cust_jane", "days": 30})
        memory = await _call(b, steps, "get_customer_memory", {"customer_id": "cust_jane"})
        merchant_id = (tx.merchant_id if tx and tx.merchant_id else "merch_jane_boutique_sg")
        await _call(b, steps, "get_merchant_reputation", {"merchant_id": merchant_id})
        await _call(b, steps, "search_policy", {"query": "cross-border travel exception declared travel window", "k": 5})

        windows = (memory or {}).get("travel_windows") or []
        if windows:
            w = windows[0]
            travel_phrase = (
                f"declared travel to {', '.join(w.get('destinations', []) or [])} "
                f"{w.get('start_date', '?')}–{w.get('end_date', '?')}"
            )
        else:
            travel_phrase = "declared travel on file"
        reason = (
            "High-value foreign transaction flagged by velocity but customer "
            f"memory shows {travel_phrase}; merchant reputation = trusted "
            "luxury boutique."
        )
        return ScoreResponse(
            verdict="approve", confidence=0.78, reason=reason,
            trace=_finalise(steps, t0),
        )

    async def _score_alex(self, tx: Optional[TransactionPayload]) -> ScoreResponse:
        steps, t0 = _empty_trace_now()
        b = self._backends
        await _call(b, steps, "get_customer_context", {"customer_id": "cust_alex"})
        await _call(b, steps, "get_devices_for_customer", {"customer_id": "cust_alex"})
        device_id = (tx.device_id if tx and tx.device_id else "dev_alex_unknown_android")
        await _call(b, steps, "get_new_device_flag", {"customer_id": "cust_alex", "device_id": device_id})
        await _call(b, steps, "get_geo_entropy", {"customer_id": "cust_alex"})
        await _call(b, steps, "find_similar_fraud", {
            "query": "new-device high-value electronics foreign card-not-present",
            "k": 5,
        })
        await _call(b, steps, "search_policy", {"query": "new-device high-value block step-up auth", "k": 5})
        return ScoreResponse(
            verdict="block", confidence=0.94,
            reason="First-seen device + impossible-travel pattern + match against known fraud cluster.",
            trace=_finalise(steps, t0),
        )

    async def _score_sarah(self, tx: Optional[TransactionPayload]) -> ScoreResponse:
        steps, t0 = _empty_trace_now()
        b = self._backends
        await _call(b, steps, "get_customer_context", {"customer_id": "cust_sarah"})
        await _call(b, steps, "get_recent_transactions",
                    {"customer_id": "cust_sarah", "days": 7})
        await _call(b, steps, "get_devices_for_customer",
                    {"customer_id": "cust_sarah"})
        await _call(b, steps, "get_customer_memory", {"customer_id": "cust_sarah"})
        await _call(b, steps, "get_pending_review", {"customer_id": "cust_sarah"})
        await _call(b, steps, "get_velocity_features", {"card_id": "card_sarah_visa"})
        merchant_id = (tx.merchant_id if tx and tx.merchant_id else "merch_sarah_tiffany_ny")
        await _call(b, steps, "get_merchant_reputation", {"merchant_id": merchant_id})
        await _call(b, steps, "get_disputes",
                    {"customer_id": "cust_sarah", "days": 180})
        await _call(b, steps, "search_policy", {
            "query": "step-up authentication travel-confirmed high-value novel merchant category",
            "k": 5,
        })
        reason = (
            "Travel + device confirmed (Manhattan trip declared, known iPhone). "
            "Value ~5x typical spend ($1,450 vs $280 p95) on a novel jewelry MCC "
            "for this customer — routing to OTP step-up rather than block to "
            "preserve a clean 18-month customer."
        )
        return ScoreResponse(
            verdict="review", confidence=0.86, reason=reason,
            trace=_finalise(steps, t0),
        )

    async def _score_generic(
        self, customer_id: str, tx: Optional[TransactionPayload]
    ) -> ScoreResponse:
        steps, t0 = _empty_trace_now()
        b = self._backends
        await _call(b, steps, "get_customer_context", {"customer_id": customer_id})
        if tx and tx.card_id:
            await _call(b, steps, "get_velocity_features", {"card_id": tx.card_id})
        await _call(b, steps, "search_policy", {"query": "default review high-confidence escalation", "k": 3})
        return ScoreResponse(
            verdict="review", confidence=0.5,
            reason=(
                f"No deterministic rule matches customer {customer_id!r}; "
                "routed to manual review pending the full Claude agent (Wave 3b)."
            ),
            trace=_finalise(steps, t0),
        )

    # --- /chat/context-surface --------------------------------------------

    async def chat_context_surface(
        self, customer_id: str, message: str,
        history: Optional[list[ChatMessage]] = None,
    ) -> ChatResponse:
        """Customer-scoped chatbot. Picks tools by keyword routing in
        ``message`` and composes a templated answer that quotes the actual
        returned data."""
        steps, t0 = _empty_trace_now()
        b = self._backends
        text = message.lower()
        answer_parts: list[str] = []

        # Always ground in the policy doc so the audience sees BOTH a policy
        # citation AND the customer-specific data — mirrors what the Claude
        # IRIS pipeline will do.
        chunks = await _call(b, steps, "search_policy", {"query": message, "k": 3})

        if any(kw in text for kw in ("travel", "trip", "going", "abroad", "overseas")):
            memory = await _call(b, steps, "get_customer_memory", {"customer_id": customer_id})
            windows = (memory or {}).get("travel_windows") or []
            if windows:
                w = windows[0]
                dest = ", ".join(w.get("destinations", []) or [])
                answer_parts.append(
                    f"Yes — Agent Memory shows {customer_id} has a declared "
                    f"travel window to {dest} from {w.get('start_date', '?')} "
                    f"to {w.get('end_date', '?')} "
                    f"(source: {w.get('source', 'unknown')})."
                )
            else:
                answer_parts.append(
                    f"No travel windows are currently on file for {customer_id}."
                )
        elif any(kw in text for kw in ("device", "phone", "laptop", "browser")):
            devices = await _call(b, steps, "get_devices_for_customer",
                                  {"customer_id": customer_id})
            summary = _first_text_field(devices)
            answer_parts.append(
                f"Devices Redis has seen for {customer_id}: "
                f"{summary or '(no devices recorded)'}"
            )
        elif any(kw in text for kw in ("recent", "transaction", "charge", "spend", "purchase")):
            txs = await _call(b, steps, "get_recent_transactions",
                              {"customer_id": customer_id, "days": 30})
            summary = _first_text_field(txs)
            answer_parts.append(
                f"Recent transactions for {customer_id} (last 30 days): "
                f"{summary or '(none in window)'}"
            )
        elif any(kw in text for kw in ("merchant", "shop", "store")):
            ctx = await _call(b, steps, "get_customer_context",
                              {"customer_id": customer_id})
            answer_parts.append(
                f"Customer profile for {customer_id}: {_first_text_field(ctx)}"
            )
        else:
            # Generic fallback: customer context.
            ctx = await _call(b, steps, "get_customer_context",
                              {"customer_id": customer_id})
            answer_parts.append(
                f"Customer profile for {customer_id}: {_first_text_field(ctx)}"
            )

        answer_parts.append(f"Policy reference: {_chunk_snippet(chunks)}")
        return ChatResponse(
            answer=" ".join(answer_parts),
            trace=_finalise(steps, t0),
        )

    # --- /chat/naive-rag --------------------------------------------------

    async def chat_naive_rag(
        self, customer_id: str, message: str,
        history: Optional[list[ChatMessage]] = None,
    ) -> ChatResponse:
        """Policy-only chatbot. Deliberately ignores ``customer_id`` for
        retrieval — the whole point of the side-by-side is to show RAG can't
        personalise. ``customer_id`` is accepted to keep the request shape
        identical to the context-surface endpoint."""
        steps, t0 = _empty_trace_now()
        b = self._backends
        chunks = await _call(b, steps, "search_policy", {"query": message, "k": 5})
        if not chunks:
            answer = (
                "I couldn't find any matching policy text. Please rephrase or "
                "ask about a bank policy topic (e.g. foreign travel, velocity, "
                "step-up authentication)."
            )
        else:
            answer = (
                f"Based on the bank's policy corpus: {_chunk_snippet(chunks, limit=500)}"
            )
        return ChatResponse(answer=answer, trace=_finalise(steps, t0))


__all__ = ["StubAgent", "LLM_MODEL"]
