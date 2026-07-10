"""Chat response cache — LangCache pillar for the Insight Chatbot.

Caches ``ChatResponse`` payloads in Redis so repeat (or semantically similar)
questions skip the LLM path. Exact match first, then cosine similarity over
stored MiniLM embeddings (same model as policy RAG).

Keys: ``cache:chat:{pipeline}:{customer_id}:{prompt_sig}``
Index: ``cache:chat:index:{pipeline}:{customer_id}`` (Redis SET)
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import math
import os
import re
from typing import Any, Literal, Optional

from app.policy_rag import default_embedder


Pipeline = Literal["context-surface", "naive-rag"]

KEY_PREFIX = "cache:chat"
INDEX_PREFIX = f"{KEY_PREFIX}:index"
DEFAULT_TTL_SECONDS = 86400
DEFAULT_SEMANTIC_THRESHOLD = 0.85
MAX_INDEX_SCAN = 64


def semantic_threshold() -> float:
    """Min cosine similarity for a local semantic cache HIT.

    Override via ``LANGCACHE_SEMANTIC_THRESHOLD`` (0.0–1.0). Lower values
    match more paraphrases; higher values are stricter.
    """
    raw = (os.environ.get("LANGCACHE_SEMANTIC_THRESHOLD") or "").strip()
    if not raw:
        return DEFAULT_SEMANTIC_THRESHOLD
    try:
        val = float(raw)
    except ValueError:
        return DEFAULT_SEMANTIC_THRESHOLD
    return max(0.0, min(1.0, val))


def normalize_prompt(message: str) -> str:
    text = message.lower().strip()
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"[?.!]+$", "", text)
    return text


def prompt_signature(message: str) -> str:
    norm = normalize_prompt(message)
    return hashlib.sha1(norm.encode("utf-8")).hexdigest()[:12]


def _key(pipeline: Pipeline, customer_id: str, sig: str) -> str:
    return f"{KEY_PREFIX}:{pipeline}:{customer_id}:{sig}"


def _index_key(pipeline: Pipeline, customer_id: str) -> str:
    return f"{INDEX_PREFIX}:{pipeline}:{customer_id}"


def _cosine(a: list[float], b: list[float]) -> float:
    if len(a) != len(b) or not a:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


async def get_exact(
    redis_client: Any,
    pipeline: Pipeline,
    customer_id: str,
    message: str,
) -> Optional[dict]:
    if redis_client is None:
        return None
    sig = prompt_signature(message)
    raw = await asyncio.to_thread(redis_client.get, _key(pipeline, customer_id, sig))
    if not raw:
        return None
    try:
        payload = json.loads(raw)
        payload["match_type"] = "exact"
        return payload
    except (json.JSONDecodeError, TypeError, ValueError):
        return None


async def search_semantic(
    redis_client: Any,
    pipeline: Pipeline,
    customer_id: str,
    message: str,
    embedder: Any = None,
) -> Optional[dict]:
    """Scan recent index entries for a cosine-similar prompt."""
    if redis_client is None:
        return None
    norm = normalize_prompt(message)
    if not norm:
        return None
    embed = embedder or default_embedder
    try:
        query_vec = embed([norm])[0]
    except Exception:  # noqa: BLE001
        return None

    idx = _index_key(pipeline, customer_id)

    def _scan() -> Optional[dict]:
        members = list(redis_client.smembers(idx))[:MAX_INDEX_SCAN]
        best_score = 0.0
        best_raw: Optional[str] = None
        for member_key in members:
            raw = redis_client.get(member_key)
            if not raw:
                continue
            try:
                payload = json.loads(raw)
            except (json.JSONDecodeError, TypeError, ValueError):
                continue
            emb = payload.get("embedding")
            if not isinstance(emb, list):
                continue
            score = _cosine(query_vec, emb)
            if score > best_score:
                best_score = score
                best_raw = raw
        if best_raw is None or best_score < semantic_threshold():
            return None
        result = json.loads(best_raw)
        result["match_type"] = "semantic"
        result["similarity"] = round(best_score, 3)
        return result

    return await asyncio.to_thread(_scan)


async def get(
    redis_client: Any,
    pipeline: Pipeline,
    customer_id: str,
    message: str,
    embedder: Any = None,
) -> Optional[dict]:
    exact = await get_exact(redis_client, pipeline, customer_id, message)
    if exact:
        return exact
    return await search_semantic(redis_client, pipeline, customer_id, message, embedder)


async def put(
    redis_client: Any,
    pipeline: Pipeline,
    customer_id: str,
    message: str,
    payload: dict,
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
    embedder: Any = None,
) -> None:
    if redis_client is None:
        return
    norm = normalize_prompt(message)
    sig = prompt_signature(message)
    embed = embedder or default_embedder
    try:
        vec = embed([norm])[0]
    except Exception:  # noqa: BLE001
        vec = []

    store = dict(payload)
    store["normalized_prompt"] = norm
    store["embedding"] = vec
    raw = json.dumps(store, separators=(",", ":"))
    key = _key(pipeline, customer_id, sig)
    idx = _index_key(pipeline, customer_id)

    def _write() -> None:
        pipe = redis_client.pipeline()
        pipe.set(key, raw, ex=ttl_seconds)
        pipe.sadd(idx, key)
        pipe.execute()

    await asyncio.to_thread(_write)


async def clear(redis_client: Any, customer_id: Optional[str] = None) -> int:
    if redis_client is None:
        return 0

    def _delete_keys(pattern: str) -> int:
        cleared = 0
        batch: list[str] = []
        for key in redis_client.scan_iter(match=pattern, count=200):
            batch.append(key)
            if len(batch) >= 200:
                cleared += redis_client.delete(*batch)
                batch.clear()
        if batch:
            cleared += redis_client.delete(*batch)
        return cleared

    def _clear_all() -> int:
        cleared = 0
        payload_batch: list[str] = []
        for key in redis_client.scan_iter(match=f"{KEY_PREFIX}:*", count=200):
            if key.startswith(f"{INDEX_PREFIX}:"):
                continue
            payload_batch.append(key)
            if len(payload_batch) >= 200:
                cleared += redis_client.delete(*payload_batch)
                payload_batch.clear()
        if payload_batch:
            cleared += redis_client.delete(*payload_batch)
        cleared += _delete_keys(f"{INDEX_PREFIX}:*")
        return cleared

    def _clear_customer(cid: str) -> int:
        cleared = _delete_keys(f"{KEY_PREFIX}:*:{cid}:*")
        cleared += _delete_keys(f"{INDEX_PREFIX}:*:{cid}")
        return cleared

    if customer_id:
        return await asyncio.to_thread(_clear_customer, customer_id)
    return await asyncio.to_thread(_clear_all)


__all__ = [
    "DEFAULT_TTL_SECONDS",
    "DEFAULT_SEMANTIC_THRESHOLD",
    "KEY_PREFIX",
    "Pipeline",
    "normalize_prompt",
    "prompt_signature",
    "semantic_threshold",
    "get",
    "get_exact",
    "put",
    "clear",
]
