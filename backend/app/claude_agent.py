"""Real Claude tool-use agent (Wave 3b).

Mirrors :class:`app.stub_agent.StubAgent`'s public interface so the API
layer can swap between the two via ``AGENT_MODE``. Drives an Anthropic
``messages.create`` loop with ``tools=AGENT_TOOL_SCHEMAS`` until Claude
emits a final assistant message (``stop_reason != "tool_use"``).

Every LLM round-trip and every tool invocation lands as a ``TraceStep`` on
the returned ``AgentTrace`` — the frontend renders both LLM steps
(``component="llm"``) and tool steps (``component="<redis layer>"``).
"""

from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Any, AsyncIterator, Optional

from anthropic import AsyncAnthropic

from app.agent_tools import AGENT_TOOL_SCHEMAS, Backends, call_tool
from app.schemas import (
    AgentTrace,
    ChatMessage,
    ChatResponse,
    ScoreResponse,
    TraceStep,
    TransactionPayload,
    Verdict,
)


DEFAULT_MODEL = "claude-sonnet-4-5-20250929"
MAX_ITERATIONS = 8
MAX_TOKENS = 1024

_PROMPTS_DIR = Path(__file__).parent / "prompts"


def _load_prompt(name: str) -> str:
    return (_PROMPTS_DIR / name).read_text(encoding="utf-8")


# The naive-RAG bot may only see ``search_policy``.
_NAIVE_TOOLS: list[dict[str, Any]] = [
    t for t in AGENT_TOOL_SCHEMAS if t["name"] == "search_policy"
]
assert len(_NAIVE_TOOLS) == 1, "search_policy must be in AGENT_TOOL_SCHEMAS"


# ---------- helpers -------------------------------------------------------

def _block_to_dict(block: Any) -> dict[str, Any]:
    """Round-trip a content block from the SDK into JSON-serialisable dict."""
    if hasattr(block, "model_dump"):
        return block.model_dump()
    return dict(block)


def _serialise_tool_result(payload: Any) -> str:
    """Best-effort JSON string of a tool's return value for Claude to read."""
    try:
        return json.dumps(payload, default=str)
    except Exception:  # noqa: BLE001
        return json.dumps({"value": str(payload)})


def _format_transaction(tx: Optional[TransactionPayload]) -> str:
    if tx is None:
        return "(no transaction payload provided)"
    fields = tx.model_dump(exclude_none=True)
    if not fields:
        return "(empty transaction payload)"
    return "\n".join(f"  {k}: {v}" for k, v in fields.items())


def _history_to_messages(history: Optional[list[ChatMessage]]) -> list[dict[str, Any]]:
    if not history:
        return []
    return [{"role": m.role, "content": m.content} for m in history]


_VERDICT_VALUES = ("approve", "review", "block")
_VERDICT_REGEX = re.compile(
    r'"verdict"\s*:\s*"(approve|review|block)"', re.IGNORECASE,
)
_CONFIDENCE_REGEX = re.compile(r'"confidence"\s*:\s*([0-9]*\.?[0-9]+)')


def _find_top_level_json_objects(s: str) -> list[str]:
    """Return every balanced top-level ``{...}`` substring in ``s``.

    A naive ``find("{")`` / ``rfind("}")`` scan can either grab the wrong
    block (when a markdown preamble has its own ``{``) or merge two
    independent objects together (when Claude appends a prose JSON
    afterthought). A real balanced scan that respects JSON string quoting
    is the only correct way to enumerate candidates.
    """
    out: list[str] = []
    depth = 0
    start = -1
    i = 0
    n = len(s)
    in_str = False
    while i < n:
        c = s[i]
        if in_str:
            if c == "\\" and i + 1 < n:
                i += 2
                continue
            if c == '"':
                in_str = False
        else:
            if c == '"':
                in_str = True
            elif c == "{":
                if depth == 0:
                    start = i
                depth += 1
            elif c == "}":
                if depth > 0:
                    depth -= 1
                    if depth == 0 and start != -1:
                        out.append(s[start : i + 1])
                        start = -1
        i += 1
    return out


def _escape_unescaped_newlines_in_strings(s: str) -> str:
    """Convert raw ``\\n`` / ``\\r`` / ``\\t`` inside JSON string literals
    to their escaped form so ``json.loads`` can parse them.

    Claude is instructed to emit ``\\n`` for line breaks inside the
    ``reason`` field, but it occasionally lapses into raw newlines when
    the prompt asks for multi-paragraph markdown. The rest of the JSON
    structure stays untouched.
    """
    out: list[str] = []
    in_str = False
    i = 0
    n = len(s)
    while i < n:
        c = s[i]
        if in_str:
            if c == "\\" and i + 1 < n:
                out.append(c)
                out.append(s[i + 1])
                i += 2
                continue
            if c == '"':
                in_str = False
                out.append(c)
            elif c == "\n":
                out.append("\\n")
            elif c == "\r":
                out.append("\\r")
            elif c == "\t":
                out.append("\\t")
            else:
                out.append(c)
        else:
            if c == '"':
                in_str = True
            out.append(c)
        i += 1
    return "".join(out)


def _try_load_json(candidate: str) -> Optional[dict[str, Any]]:
    """Best-effort ``json.loads``. Retries once with raw whitespace
    inside string literals re-escaped before giving up.
    """
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        pass
    try:
        return json.loads(_escape_unescaped_newlines_in_strings(candidate))
    except json.JSONDecodeError:
        return None


def _parse_verdict_payload(text: str) -> tuple[Verdict, float, str]:
    """Extract ``{verdict, confidence, reason}`` from Claude's final message.

    Hardened in Wave 7k.1 to survive three observed failure modes:

    * Raw newlines inside the JSON ``reason`` string — pre-escape them
      before retrying ``json.loads``.
    * Markdown preamble or code fence wrapping the JSON — strip fences and
      enumerate every balanced top-level ``{...}`` substring, preferring
      the LAST one that carries a valid ``verdict``.
    * Prose afterthought trailing the JSON — same balanced-brace scan
      ignores anything outside top-level objects.

    Final fallback: regex-extract just ``verdict`` (and optionally
    ``confidence``) so a malformed body never silently degrades to a
    ``review`` verdict on what should have been a clean ``approve`` /
    ``block``.
    """
    candidate = text.strip()
    # Strip ```json fences if present.
    if candidate.startswith("```"):
        candidate = candidate.strip("`")
        if candidate.lower().startswith("json"):
            candidate = candidate[4:]
        candidate = candidate.strip()

    obj: Optional[dict[str, Any]] = _try_load_json(candidate)

    if obj is None:
        # Enumerate every balanced top-level {...} block and prefer the
        # LAST one that has a valid verdict — Claude sometimes precedes
        # the real JSON with an example or a partial draft.
        for block in reversed(_find_top_level_json_objects(candidate)):
            parsed = _try_load_json(block)
            if isinstance(parsed, dict) and parsed.get("verdict") in _VERDICT_VALUES:
                obj = parsed
                break

    if obj is None:
        # Last-ditch: regex out the verdict so the demo doesn't silently
        # degrade to a manual-review fallback on a malformed body.
        m = _VERDICT_REGEX.search(candidate)
        if m is None:
            raise ValueError(f"final message is not JSON: {text!r}")
        verdict = m.group(1).lower()
        conf_m = _CONFIDENCE_REGEX.search(candidate)
        confidence = float(conf_m.group(1)) if conf_m else 0.5
        confidence = max(0.0, min(1.0, confidence))
        return verdict, confidence, candidate.strip()

    verdict = obj.get("verdict")
    if verdict not in _VERDICT_VALUES:
        raise ValueError(f"invalid verdict {verdict!r} in final message")
    confidence = float(obj.get("confidence", 0.0))
    confidence = max(0.0, min(1.0, confidence))
    reason = str(obj.get("reason", "")).strip()
    if not reason:
        raise ValueError("missing reason in final message")
    return verdict, confidence, reason


# ---------- agent --------------------------------------------------------

class ClaudeAgent:
    """Tool-use Claude agent. Same public interface as ``StubAgent``."""

    def __init__(
        self,
        backends: Backends,
        *,
        client: Optional[AsyncAnthropic] = None,
        model: Optional[str] = None,
    ) -> None:
        self._backends = backends
        self._client = client or AsyncAnthropic()
        self._model = model or os.environ.get("ANTHROPIC_MODEL") or DEFAULT_MODEL

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
        """Same behaviour as :meth:`score` but yields progress events.

        Event shapes:
          ``{"type": "thinking", "round": N}`` — emitted before each LLM
          ``messages.create`` call (presenter beat during the 5–10s waits).
          ``{"type": "step", "step": TraceStep}`` — emitted as each LLM round
          and each tool invocation resolves.
          ``{"type": "final", "response": ScoreResponse}`` — terminal event.
        """
        system = _load_prompt("fraud_agent.md")
        user_text = (
            "Decide on the following transaction.\n\n"
            f"Customer ID: {customer_id}\n"
            f"Transaction:\n{_format_transaction(transaction)}\n\n"
            "Use your tools to gather context (memory, recent transactions, "
            "device history, velocity, similar fraud, policy) as needed, then "
            "return the final JSON object as specified."
        )
        messages: list[dict[str, Any]] = [{"role": "user", "content": user_text}]
        steps: list[TraceStep] = []
        t0 = time.perf_counter()
        final_text = ""
        async for ev in self._run_loop_events(system, messages, AGENT_TOOL_SCHEMAS, steps):
            if ev["type"] == "final_text":
                final_text = ev["text"]
            else:
                yield ev
        try:
            verdict, confidence, reason = _parse_verdict_payload(final_text)
        except ValueError:
            verdict, confidence, reason = (
                "review",
                0.5,
                f"Agent did not return a parseable verdict. Raw response: {final_text[:400]}",
            )
        yield {
            "type": "final",
            "response": ScoreResponse(
                verdict=verdict, confidence=confidence, reason=reason,
                trace=self._finalise(steps, t0),
            ),
        }

    # --- /chat/context-surface --------------------------------------------

    async def chat_context_surface(
        self,
        customer_id: str,
        message: str,
        history: Optional[list[ChatMessage]] = None,
    ) -> ChatResponse:
        system = _load_prompt("chat_context_surface.md")
        msgs = _history_to_messages(history)
        msgs.append({
            "role": "user",
            "content": (
                f"Customer being served: {customer_id}\n\n"
                f"User question: {message}"
            ),
        })
        steps: list[TraceStep] = []
        t0 = time.perf_counter()
        answer = await self._run_loop(system, msgs, AGENT_TOOL_SCHEMAS, steps)
        return ChatResponse(answer=answer, trace=self._finalise(steps, t0))

    # --- /chat/naive-rag --------------------------------------------------

    async def chat_naive_rag(
        self,
        customer_id: str,
        message: str,
        history: Optional[list[ChatMessage]] = None,
    ) -> ChatResponse:
        # Deliberately do NOT pass customer_id into the LLM context — naive
        # RAG has no per-customer knowledge by design.
        system = _load_prompt("chat_naive_rag.md")
        msgs = _history_to_messages(history)
        msgs.append({"role": "user", "content": f"User question: {message}"})
        steps: list[TraceStep] = []
        t0 = time.perf_counter()
        answer = await self._run_loop(system, msgs, _NAIVE_TOOLS, steps)
        return ChatResponse(answer=answer, trace=self._finalise(steps, t0))

    # --- internals --------------------------------------------------------

    def _finalise(self, steps: list[TraceStep], t0: float) -> AgentTrace:
        total = int((time.perf_counter() - t0) * 1000)
        return AgentTrace(steps=steps, total_latency_ms=total, llm_model=self._model)

    async def _run_loop(
        self,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        steps: list[TraceStep],
    ) -> str:
        """Drive the messages.create / tool_result loop until Claude stops.

        Thin collector around :meth:`_run_loop_events` for callers (chat
        endpoints) that don't need progressive event emission.
        """
        final_text = ""
        async for ev in self._run_loop_events(system, messages, tools, steps):
            if ev["type"] == "final_text":
                final_text = ev["text"]
        return final_text

    async def _run_loop_events(
        self,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        steps: list[TraceStep],
    ) -> AsyncIterator[dict[str, Any]]:
        """Generator version of :meth:`_run_loop`.

        Yields ``thinking`` events before each LLM call and ``step`` events
        as each LLM round + tool call resolves. Terminates with a single
        ``final_text`` event carrying the agent's final assistant text.
        """
        round_num = 0
        for _ in range(MAX_ITERATIONS):
            round_num += 1
            yield {"type": "thinking", "round": round_num}
            llm_start = time.perf_counter()
            resp = await self._client.messages.create(
                model=self._model,
                max_tokens=MAX_TOKENS,
                system=system,
                tools=tools,
                messages=messages,
            )
            llm_ms = int((time.perf_counter() - llm_start) * 1000)

            usage = getattr(resp, "usage", None)
            in_tok = int(getattr(usage, "input_tokens", 0) or 0) if usage else 0
            out_tok = int(getattr(usage, "output_tokens", 0) or 0) if usage else 0
            stop_reason = getattr(resp, "stop_reason", None)
            llm_step = TraceStep(
                component="llm",
                tool="anthropic.messages.create",
                input={"model": self._model, "num_tools": len(tools)},
                output_summary=(
                    f"stop={stop_reason} in_tokens={in_tok} out_tokens={out_tok}"
                ),
                output_data={
                    "stop_reason": stop_reason,
                    "input_tokens": in_tok,
                    "output_tokens": out_tok,
                },
                latency_ms=llm_ms,
                redis_keys_touched=[],
            )
            steps.append(llm_step)
            yield {"type": "step", "step": llm_step}

            content = list(resp.content or [])
            tool_uses = [b for b in content if getattr(b, "type", None) == "tool_use"]

            if stop_reason != "tool_use" or not tool_uses:
                # Final assistant message — collect any text blocks.
                text_parts = [
                    b.text for b in content
                    if getattr(b, "type", None) == "text"
                ]
                yield {"type": "final_text", "text": "\n".join(text_parts).strip()}
                return

            # Echo the assistant turn back into the conversation, then
            # execute every tool_use and feed the results back as one
            # ``user`` message containing all ``tool_result`` blocks.
            messages.append({
                "role": "assistant",
                "content": [_block_to_dict(b) for b in content],
            })
            tool_result_blocks: list[dict[str, Any]] = []
            for tu in tool_uses:
                tool_name = getattr(tu, "name", "")
                tool_input = getattr(tu, "input", {}) or {}
                try:
                    payload, trace = await call_tool(
                        tool_name, dict(tool_input), backends=self._backends,
                    )
                    steps.append(trace)
                    yield {"type": "step", "step": trace}
                    result_text = _serialise_tool_result(payload)
                    is_error = False
                except Exception as exc:  # noqa: BLE001
                    result_text = json.dumps({"error": str(exc)})
                    is_error = True
                tool_result_blocks.append({
                    "type": "tool_result",
                    "tool_use_id": getattr(tu, "id", ""),
                    "content": result_text,
                    "is_error": is_error,
                })
            messages.append({"role": "user", "content": tool_result_blocks})

        yield {
            "type": "final_text",
            "text": (
                "Agent did not converge to a final answer within the iteration "
                "budget. Returning a manual-review fallback."
            ),
        }


__all__ = ["ClaudeAgent", "DEFAULT_MODEL"]
