"""Frozen Pydantic schemas — the contract between the backend, the (later)
Claude implementation in Wave 3b, and the Wave 4 Next.js UI.

DO NOT change field names, types, or ordering without coordinating with the
frontend agent. The UI consumes these exact shapes and will silently misrender
if anything drifts.

Components:

- ``TraceStep`` — one tool invocation as the IRIS side-panels render it.
- ``AgentTrace`` — ordered list of ``TraceStep`` for a single agent turn.
- ``ScoreRequest`` / ``ScoreResponse`` — ``POST /agent/score``.
- ``ChatMessage`` / ``ChatRequest`` / ``ChatResponse`` —
  ``POST /chat/context-surface`` and ``POST /chat/naive-rag``.

The ``llm_model`` slot is ``"stub-deterministic"`` during Wave 3a and switches
to ``"claude-sonnet-..."`` in Wave 3b without any other schema change.
"""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


Component = Literal[
    "context_retriever",
    "feature_store",
    "agent_memory",
    "policy_rag",
    "llm",
]


Verdict = Literal["approve", "review", "block"]


class TraceStep(BaseModel):
    """One observable step the agent took during a single turn.

    All fields are required; ``output_data`` may be ``None`` when the tool
    returned nothing displayable but the call itself is still worth showing
    (e.g. an empty agent-memory lookup).
    """

    component: Component = Field(..., description="Which Redis IRIS layer this step touched.")
    tool: str = Field(..., description="Concrete tool/function name, e.g. 'get_recent_transactions'.")
    input: dict[str, Any] = Field(default_factory=dict, description="Arguments passed to the tool.")
    output_summary: str = Field(..., description="Short human-readable summary for the side panel header.")
    output_data: Optional[dict[str, Any]] = Field(
        default=None,
        description="Full payload for the expandable detail view; None if not displayable.",
    )
    latency_ms: int = Field(..., ge=0, description="Wall-clock latency of this step in ms.")
    redis_keys_touched: list[str] = Field(
        default_factory=list,
        description="Redis keys read or written — drives the Redis Insight side-by-side moment.",
    )


class AgentTrace(BaseModel):
    """Ordered execution trace for one agent turn."""

    steps: list[TraceStep] = Field(default_factory=list)
    total_latency_ms: int = Field(..., ge=0, description="Sum of step latencies + dispatch overhead.")
    llm_model: str = Field(
        ...,
        description="Model identifier — 'stub-deterministic' in Wave 3a, real Claude model id in 3b.",
    )


# --- /agent/score ----------------------------------------------------------

class TransactionPayload(BaseModel):
    """In-flight transaction the agent is asked to rule on.

    All fields are optional individually so the UI can submit a partial form,
    but the stub agent's verdict precision depends on having ``merchant_id``,
    ``country``, ``amount`` and ``currency`` present.
    """

    amount: Optional[float] = None
    currency: Optional[str] = None
    merchant_id: Optional[str] = None
    merchant_name: Optional[str] = None
    country: Optional[str] = None
    city: Optional[str] = None
    card_id: Optional[str] = None
    device_id: Optional[str] = None
    is_card_present: Optional[bool] = None


class ScoreRequest(BaseModel):
    """Score a transaction. Provide a ``transaction_id`` to look up the tx via
    the Context Retriever, or a full ``transaction`` payload to score directly.
    ``customer_id`` is required when ``transaction`` is provided."""

    transaction_id: Optional[str] = None
    customer_id: Optional[str] = None
    transaction: Optional[TransactionPayload] = None


class ScoreResponse(BaseModel):
    verdict: Verdict
    confidence: float = Field(..., ge=0.0, le=1.0)
    reason: str
    trace: AgentTrace
    # Wave 7n: surfaced when this response was served from the Redis verdict
    # cache. ``cache_latency_ms`` is the round-trip on the cache GET so the
    # frontend can render the "Served from Redis · 3ms" badge.
    cached: bool = False
    cache_latency_ms: Optional[int] = None


class VerdictFastResponse(BaseModel):
    """Deterministic, LLM-free verdict (Wave 7f+). Same request shape as
    ``/agent/score``; ``signals`` carries human-readable rule strings the
    UI surfaces under the verdict chip."""

    verdict: Verdict
    confidence: float = Field(..., ge=0.0, le=1.0)
    signals: list[str] = Field(default_factory=list)
    total_latency_ms: int = Field(..., ge=0)


class OtpConfirmRequest(BaseModel):
    """Simulated step-up OTP confirmation request (Wave 7i)."""

    transaction_id: str


class OtpConfirmResponse(BaseModel):
    """Simulated step-up OTP confirmation response. Demo determinism: the
    OTP always confirms — there's no fail path."""

    confirmed: bool
    final_verdict: Verdict
    step_up_used: bool


# --- /chat/* ---------------------------------------------------------------

class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    customer_id: str
    message: str
    history: list[ChatMessage] = Field(default_factory=list)


class ChatResponse(BaseModel):
    answer: str
    trace: AgentTrace


__all__ = [
    "Component",
    "Verdict",
    "TraceStep",
    "AgentTrace",
    "TransactionPayload",
    "ScoreRequest",
    "ScoreResponse",
    "VerdictFastResponse",
    "OtpConfirmRequest",
    "OtpConfirmResponse",
    "ChatMessage",
    "ChatRequest",
    "ChatResponse",
]
