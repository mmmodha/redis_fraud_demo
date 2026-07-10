"""Chatbot endpoints — the side-by-side IRIS-vs-RAG moment.

Both endpoints share the ``ChatRequest`` / ``ChatResponse`` schemas and
optionally serve from the LangCache layer (local Redis semantic cache by
default; managed LangCache when credentials are configured).
"""

from __future__ import annotations

import time
from typing import Any, Literal, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Response

from app import chat_cache, langcache_client
from app.api import deps
from app.api.deps import Agent, get_agent
from app.schemas import AgentTrace, ChatRequest, ChatResponse, TraceStep


router = APIRouter(prefix="/chat", tags=["chat"])

Pipeline = Literal["context-surface", "naive-rag"]

# Demo fallbacks when stub agent returns no LLM token counts.
_DEFAULT_TOKENS: dict[Pipeline, tuple[int, int]] = {
    "context-surface": (820, 180),
    "naive-rag": (620, 140),
}


def _safe_redis() -> Optional[Any]:
    try:
        return deps._redis()
    except RuntimeError:
        return None


def _extract_tokens(trace: AgentTrace, pipeline: Pipeline) -> tuple[int, int]:
    in_t, out_t = 0, 0
    for step in trace.steps:
        if step.component != "llm" or not step.output_data:
            continue
        in_t += int(step.output_data.get("input_tokens") or 0)
        out_t += int(step.output_data.get("output_tokens") or 0)
    if in_t == 0 and out_t == 0:
        return _DEFAULT_TOKENS[pipeline]
    return in_t, out_t


def _enrich_response(
    resp: ChatResponse,
    pipeline: Pipeline,
    *,
    cached: bool,
    cache_latency_ms: Optional[int],
    cache_backend: Optional[str],
    cache_match_type: Optional[str] = None,
    cache_similarity: Optional[float] = None,
    tokens_saved_input: Optional[int] = None,
    tokens_saved_output: Optional[int] = None,
) -> ChatResponse:
    data = resp.model_dump()
    in_t, out_t = _extract_tokens(resp.trace, pipeline)
    data.update({
        "cached": cached,
        "cache_latency_ms": cache_latency_ms,
        "cache_backend": cache_backend,
        "cache_match_type": cache_match_type,
        "cache_similarity": cache_similarity,
        "input_tokens": 0 if cached else in_t,
        "output_tokens": 0 if cached else out_t,
        "tokens_saved_input": tokens_saved_input,
        "tokens_saved_output": tokens_saved_output,
    })
    return ChatResponse(**data)


def _hit_from_payload(
    payload: dict,
    pipeline: Pipeline,
    cache_latency_ms: int,
    backend: str,
) -> ChatResponse:
    stored = payload.get("response")
    if not isinstance(stored, dict):
        raise ValueError("invalid cache payload")
    resp = ChatResponse(**stored)
    match_type = payload.get("match_type")
    saved_in = int(payload.get("input_tokens") or _extract_tokens(resp.trace, pipeline)[0])
    saved_out = int(payload.get("output_tokens") or _extract_tokens(resp.trace, pipeline)[1])
    return _enrich_response(
        resp,
        pipeline,
        cached=True,
        cache_latency_ms=cache_latency_ms,
        cache_backend=backend,  # type: ignore[arg-type]
        cache_match_type=match_type if match_type in ("exact", "semantic") else "exact",
        cache_similarity=payload.get("similarity"),
        tokens_saved_input=saved_in,
        tokens_saved_output=saved_out,
    )


async def _cached_chat(
    pipeline: Pipeline,
    req: ChatRequest,
    agent: Agent,
    agent_fn: Any,
    response: Response,
    bypass: bool,
) -> ChatResponse:
    redis_client = _safe_redis()
    lc_cfg = langcache_client.config_from_env()

    if not bypass:
        # Managed LangCache first when configured.
        if lc_cfg is not None:
            t0 = time.perf_counter()
            hit = langcache_client.search(lc_cfg, req.message)
            latency = int((time.perf_counter() - t0) * 1000)
            if hit and isinstance(hit.get("response"), str):
                # Reconstruct minimal trace for cached answer.
                trace = AgentTrace(
                    steps=[
                        TraceStep(
                            component="llm",
                            tool="langcache_hit",
                            input={"prompt": req.message},
                            output_summary="LangCache HIT — LLM skipped",
                            output_data={"cache_hit": True},
                            latency_ms=latency,
                            redis_keys_touched=[],
                        ),
                    ],
                    total_latency_ms=latency,
                    llm_model="langcache",
                )
                resp = ChatResponse(answer=hit["response"], trace=trace)
                saved_in, saved_out = _DEFAULT_TOKENS[pipeline]
                match_type = hit.get("match_type")
                if match_type not in ("exact", "semantic"):
                    match_type = "semantic"
                result = _enrich_response(
                    resp,
                    pipeline,
                    cached=True,
                    cache_latency_ms=latency,
                    cache_backend="langcache",
                    cache_match_type=match_type,
                    cache_similarity=hit.get("similarity"),
                    tokens_saved_input=saved_in,
                    tokens_saved_output=saved_out,
                )
                response.headers["X-Cache"] = "HIT"
                response.headers["X-Cache-Backend"] = "langcache"
                return result

        if redis_client is not None:
            t0 = time.perf_counter()
            try:
                payload = await chat_cache.get(
                    redis_client, pipeline, req.customer_id, req.message,
                )
            except Exception:  # noqa: BLE001
                payload = None
            latency = int((time.perf_counter() - t0) * 1000)
            if payload and isinstance(payload.get("response"), dict):
                result = _hit_from_payload(payload, pipeline, latency, "local")
                response.headers["X-Cache"] = "HIT"
                response.headers["X-Cache-Backend"] = "local"
                response.headers["X-Cache-Latency-Ms"] = str(latency)
                return result

    try:
        live: ChatResponse = await agent_fn(
            customer_id=req.customer_id,
            message=req.message,
            history=req.history,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    in_t, out_t = _extract_tokens(live.trace, pipeline)
    result = _enrich_response(
        live,
        pipeline,
        cached=False,
        cache_latency_ms=None,
        cache_backend=None,
    )
    response.headers["X-Cache"] = "BYPASS" if bypass else "MISS"

    if redis_client is not None and not bypass:
        store_payload = {
            "response": live.model_dump(),
            "input_tokens": in_t,
            "output_tokens": out_t,
        }
        try:
            await chat_cache.put(
                redis_client, pipeline, req.customer_id, req.message, store_payload,
            )
        except Exception:  # noqa: BLE001
            pass

    if lc_cfg is not None and not bypass:
        langcache_client.store(lc_cfg, req.message, live.answer)

    return result


def _is_bypass(x_bypass_cache: Optional[str]) -> bool:
    return bool(x_bypass_cache) and x_bypass_cache.strip().lower() in (
        "1", "true", "yes", "on",
    )


@router.post("/context-surface", response_model=ChatResponse)
async def chat_context_surface(
    req: ChatRequest,
    response: Response,
    agent: Agent = Depends(get_agent),
    x_bypass_cache: Optional[str] = Header(default=None),
) -> ChatResponse:
    if not req.customer_id:
        raise HTTPException(status_code=400, detail="customer_id is required")
    return await _cached_chat(
        "context-surface",
        req,
        agent,
        agent.chat_context_surface,
        response,
        _is_bypass(x_bypass_cache),
    )


@router.post("/naive-rag", response_model=ChatResponse)
async def chat_naive_rag(
    req: ChatRequest,
    response: Response,
    agent: Agent = Depends(get_agent),
    x_bypass_cache: Optional[str] = Header(default=None),
) -> ChatResponse:
    return await _cached_chat(
        "naive-rag",
        req,
        agent,
        agent.chat_naive_rag,
        response,
        _is_bypass(x_bypass_cache),
    )


@router.post("/cache/clear")
async def chat_cache_clear() -> dict:
    redis_client = _safe_redis()
    if redis_client is None:
        raise HTTPException(status_code=503, detail="REDIS_URL is not set")
    cleared = await chat_cache.clear(redis_client, None)
    return {"cleared": cleared}
