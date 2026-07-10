"""POST /agent/score — fraud-detection agent entry point.

Wave 3a returns a deterministic stub verdict for the three hero customers
(Mike / Jane / Alex) and a generic ``review`` for anyone else. The trace
records on the response are real — every step ran against the actual IRIS
backend. See ``backend/app/stub_agent.py`` for the per-hero logic.
"""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any, AsyncIterator, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app import chat_cache, verdict_cache
from app.agent_tools import call_tool
from app.api.deps import Agent, _redis, get_agent, get_backends
from app.policy_engine import evaluate_verdict_fast
from app.schemas import (
    OtpConfirmRequest,
    OtpConfirmResponse,
    ScoreRequest,
    ScoreResponse,
    VerdictFastResponse,
)


router = APIRouter(prefix="/agent", tags=["agent"])


def _safe_redis() -> Optional[Any]:
    """Return the shared Redis client, or ``None`` if REDIS_URL is unset.

    The cache is best-effort — a missing/broken Redis must never break the
    MISS path (existing behaviour). Callers swallow this as a non-fatal."""
    try:
        return _redis()
    except RuntimeError:
        return None


def _is_bypass(
    x_bypass_cache: Optional[str], nocache: Optional[str],
) -> bool:
    """Wave 7n: Shift+click on a hero card sends ``X-Bypass-Cache: 1`` so the
    presenter can force a fresh agent run while leaving the cache populated.
    ``?nocache=1`` is the URL-only fallback.
    """
    def _truthy(v: Optional[str]) -> bool:
        return bool(v) and v.strip().lower() in ("1", "true", "yes", "on")
    return _truthy(x_bypass_cache) or _truthy(nocache)


def _resolve_customer_id(req: ScoreRequest) -> str:
    """Caller may pass either ``customer_id`` (with an inline ``transaction``)
    or ``transaction_id`` (which would be resolved via the Context Retriever
    in Wave 3b). For Wave 3a we require ``customer_id``.
    """
    if req.customer_id:
        return req.customer_id
    if req.transaction_id:
        # Looking up a tx -> customer would go via the Context Retriever; the
        # stub keeps Wave 3a simple by requiring the caller to supply it.
        raise HTTPException(
            status_code=400,
            detail=(
                "transaction_id lookup is not implemented in the stub; "
                "supply customer_id alongside transaction_id (Wave 3b will "
                "resolve it via Context Retriever)."
            ),
        )
    raise HTTPException(status_code=400, detail="customer_id is required")


@router.post("/score", response_model=ScoreResponse)
async def score_transaction(
    req: ScoreRequest,
    response: Response,
    agent: Agent = Depends(get_agent),
    x_bypass_cache: Optional[str] = Header(default=None),
    nocache: Optional[str] = Query(default=None),
) -> ScoreResponse:
    customer_id = _resolve_customer_id(req)
    sig = verdict_cache.transaction_signature(req.transaction)
    redis_client = _safe_redis()
    bypass = _is_bypass(x_bypass_cache, nocache)

    # Cache lookup: measure the GET round-trip so we can report it. Skip
    # entirely when the caller forced a bypass.
    cached_payload: Optional[dict] = None
    cache_latency_ms: int = 0
    if redis_client is not None and not bypass:
        t0 = time.perf_counter()
        try:
            cached_payload = await verdict_cache.get(redis_client, customer_id, sig)
        except Exception:  # noqa: BLE001
            cached_payload = None
        cache_latency_ms = int((time.perf_counter() - t0) * 1000)

    if cached_payload and isinstance(cached_payload.get("response"), dict):
        cached_resp = dict(cached_payload["response"])
        cached_resp["cached"] = True
        cached_resp["cache_latency_ms"] = cache_latency_ms
        response.headers["X-Cache"] = "HIT"
        response.headers["X-Cache-Latency-Ms"] = str(cache_latency_ms)
        return ScoreResponse(**cached_resp)

    try:
        result = await agent.score(customer_id, req.transaction)
    except RuntimeError as exc:
        # Missing env vars / unreachable backends bubble up as 503.
        raise HTTPException(status_code=503, detail=str(exc))

    response.headers["X-Cache"] = "BYPASS" if bypass else "MISS"
    if redis_client is not None:
        # On bypass we still write through so the next normal click is cached
        # again with the fresh result. Preserve any existing captured stream
        # events so we don't clobber the replay buffer.
        existing_events: list = []
        if cached_payload and isinstance(cached_payload.get("events"), list):
            existing_events = cached_payload["events"]
        elif bypass:
            # Re-read once to preserve existing events under a bypass write.
            try:
                prior = await verdict_cache.get(redis_client, customer_id, sig)
                if prior and isinstance(prior.get("events"), list):
                    existing_events = prior["events"]
            except Exception:  # noqa: BLE001
                existing_events = []
        to_cache = {
            "response": result.model_dump(mode="json"),
            "events": existing_events,
        }
        try:
            await verdict_cache.put(redis_client, customer_id, sig, to_cache)
        except Exception:  # noqa: BLE001
            pass
    return result


def _serialise_event(event: dict[str, Any]) -> str:
    """Encode one agent event as a single NDJSON line (terminating \\n)."""
    etype = event.get("type")
    if etype == "step":
        payload = {"type": "step", "step": event["step"].model_dump(mode="json")}
    elif etype == "final":
        payload = {
            "type": "final",
            "response": event["response"].model_dump(mode="json"),
        }
    elif etype == "thinking":
        payload = {"type": "thinking", "round": event["round"]}
    else:
        # Pass-through for forward-compatibility (e.g. future "start" events).
        payload = event
    return json.dumps(payload, separators=(",", ":")) + "\n"


@router.post("/score/stream")
async def score_transaction_stream(
    req: ScoreRequest,
    agent: Agent = Depends(get_agent),
    x_bypass_cache: Optional[str] = Header(default=None),
    nocache: Optional[str] = Query(default=None),
) -> StreamingResponse:
    """Streaming variant of ``/agent/score``.

    Returns ``application/x-ndjson`` with one event per line as the agent
    progresses: ``thinking`` before each LLM round, ``step`` per LLM round
    and per tool call, and a terminal ``final`` event carrying the same
    ``ScoreResponse`` the non-streaming endpoint would return.

    Wave 7n: on a verdict-cache HIT, the captured event sequence is replayed
    back-to-back with a 5ms gap between events so the trace strip still
    flickers visibly (~50ms total) without re-running the LLM.
    """
    customer_id = _resolve_customer_id(req)
    sig = verdict_cache.transaction_signature(req.transaction)
    redis_client = _safe_redis()
    bypass = _is_bypass(x_bypass_cache, nocache)

    cached_payload: Optional[dict] = None
    cache_latency_ms: int = 0
    if redis_client is not None and not bypass:
        t0 = time.perf_counter()
        try:
            cached_payload = await verdict_cache.get(redis_client, customer_id, sig)
        except Exception:  # noqa: BLE001
            cached_payload = None
        cache_latency_ms = int((time.perf_counter() - t0) * 1000)

    cached_events: list[dict] = []
    if cached_payload:
        events = cached_payload.get("events")
        if isinstance(events, list) and events:
            cached_events = events

    if cached_events:
        async def gen_cached() -> AsyncIterator[bytes]:
            for ev in cached_events:
                # Annotate the final event so the frontend can show the
                # "Served from Redis" badge without sniffing headers.
                if isinstance(ev, dict) and ev.get("type") == "final" \
                        and isinstance(ev.get("response"), dict):
                    ev = dict(ev)
                    resp = dict(ev["response"])
                    resp["cached"] = True
                    resp["cache_latency_ms"] = cache_latency_ms
                    ev["response"] = resp
                yield (json.dumps(ev, separators=(",", ":")) + "\n").encode("utf-8")
                await asyncio.sleep(0.005)

        return StreamingResponse(
            gen_cached(),
            media_type="application/x-ndjson",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
                "X-Cache": "HIT",
                "X-Cache-Latency-Ms": str(cache_latency_ms),
            },
        )

    async def gen_live() -> AsyncIterator[bytes]:
        captured: list[dict] = []
        completed_ok = False
        try:
            async for event in agent.score_stream(customer_id, req.transaction):
                line = _serialise_event(event)
                try:
                    captured.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
                if event.get("type") == "final":
                    completed_ok = True
                yield line.encode("utf-8")
        except RuntimeError as exc:
            yield (
                json.dumps({"type": "error", "message": str(exc)}) + "\n"
            ).encode("utf-8")
            return
        # Only cache on a clean final event — never cache partial / failed streams.
        if completed_ok and redis_client is not None:
            final_event = next(
                (e for e in reversed(captured) if e.get("type") == "final"), None,
            )
            response_payload = (
                final_event.get("response") if final_event else {}
            ) or {}
            try:
                await verdict_cache.put(
                    redis_client, customer_id, sig,
                    {"response": response_payload, "events": captured},
                )
            except Exception:  # noqa: BLE001
                pass

    return StreamingResponse(
        gen_live(),
        media_type="application/x-ndjson",
        headers={
            # Disable proxy buffering so each line flushes immediately —
            # this is what makes the right-rail panels light up live on stage.
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "X-Cache": "BYPASS" if bypass else "MISS",
        },
    )


# --- Wave 7n: presenter cache-clear affordance -----------------------------

class CacheClearRequest(BaseModel):
    """Optional body for ``POST /agent/cache/clear``.

    ``customer_id`` scopes the clear to one hero; absent → clear all verdict
    cache keys."""
    customer_id: Optional[str] = None


class CacheClearResponse(BaseModel):
    cleared: int


@router.post("/cache/clear", response_model=CacheClearResponse)
async def cache_clear(req: Optional[CacheClearRequest] = None) -> CacheClearResponse:
    redis_client = _safe_redis()
    if redis_client is None:
        raise HTTPException(status_code=503, detail="REDIS_URL is not set")
    customer_id = req.customer_id if req else None
    cleared = await verdict_cache.clear(redis_client, customer_id)
    chat_cleared = await chat_cache.clear(redis_client, customer_id)
    return CacheClearResponse(cleared=cleared + chat_cleared)


@router.post("/verdict-fast", response_model=VerdictFastResponse)
async def verdict_fast(req: ScoreRequest) -> VerdictFastResponse:
    """Deterministic verdict (no LLM). Same request shape as ``/agent/score``.

    Pulls ``pending_review:{customer_id}`` and ``mem:{customer_id}`` via the
    existing tool dispatcher, runs the policy engine, and returns the verdict
    + signals in well under 300 ms.
    """
    customer_id = _resolve_customer_id(req)
    try:
        backends = await get_backends()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    t0 = time.perf_counter()
    try:
        pending, _ = await call_tool(
            "get_pending_review", {"customer_id": customer_id}, backends=backends,
        )
        memory, _ = await call_tool(
            "get_customer_memory", {"customer_id": customer_id}, backends=backends,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    result = evaluate_verdict_fast(
        customer_id=customer_id,
        pending_review=pending,
        memory=memory,
    )
    total_latency_ms = int((time.perf_counter() - t0) * 1000)
    return VerdictFastResponse(
        verdict=result["verdict"],
        confidence=result["confidence"],
        signals=result["signals"],
        total_latency_ms=total_latency_ms,
    )


@router.post("/otp-confirm", response_model=OtpConfirmResponse)
async def otp_confirm(req: OtpConfirmRequest) -> OtpConfirmResponse:
    """Simulated step-up OTP confirmation (Wave 7i).

    Demo determinism: 1s simulated delay, always confirms. Frontend fires
    this 1s after a REVIEW verdict lands; the resolved response flips the
    on-screen verdict card to ``APPROVED · Step-Up Used``.
    """
    if not req.transaction_id:
        raise HTTPException(status_code=400, detail="transaction_id is required")
    await asyncio.sleep(1.0)
    return OtpConfirmResponse(
        confirmed=True, final_verdict="approve", step_up_used=True,
    )
