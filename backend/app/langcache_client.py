"""Optional managed Redis LangCache client.

When ``LANGCACHE_SERVER_URL``, ``LANGCACHE_CACHE_ID``, and
``LANGCACHE_API_KEY`` are all set, chat endpoints search/store via the
managed LangCache service. Otherwise this module is a no-op and the local
Redis cache in :mod:`app.chat_cache` handles everything.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Optional


DEFAULT_SIMILARITY_THRESHOLD = 0.85


@dataclass(frozen=True)
class LangCacheConfig:
    server_url: str
    cache_id: str
    api_key: str
    similarity_threshold: float


def similarity_threshold() -> float:
    """Min similarity score for managed LangCache semantic HITs.

    Override via ``LANGCACHE_SIMILARITY_THRESHOLD`` (0.0–1.0).
    """
    raw = (os.environ.get("LANGCACHE_SIMILARITY_THRESHOLD") or "").strip()
    if not raw:
        return DEFAULT_SIMILARITY_THRESHOLD
    try:
        val = float(raw)
    except ValueError:
        return DEFAULT_SIMILARITY_THRESHOLD
    return max(0.0, min(1.0, val))


def config_from_env() -> Optional[LangCacheConfig]:
    url = (os.environ.get("LANGCACHE_SERVER_URL") or "").strip()
    cache_id = (os.environ.get("LANGCACHE_CACHE_ID") or "").strip()
    api_key = (os.environ.get("LANGCACHE_API_KEY") or "").strip()
    if url and cache_id and api_key:
        return LangCacheConfig(
            server_url=url,
            cache_id=cache_id,
            api_key=api_key,
            similarity_threshold=similarity_threshold(),
        )
    return None


def _client(cfg: LangCacheConfig) -> Any:
    from langcache import LangCache  # type: ignore[import-untyped]

    return LangCache(
        server_url=cfg.server_url,
        cache_id=cfg.cache_id,
        api_key=cfg.api_key,
    )


def _extract_response(hit: Any) -> Optional[str]:
    if isinstance(hit, dict):
        for key in ("response", "data", "answer", "content"):
            val = hit.get(key)
            if isinstance(val, str) and val.strip():
                return val
        return None
    for attr in ("response", "data", "answer", "content"):
        val = getattr(hit, attr, None)
        if isinstance(val, str) and val.strip():
            return val
    return None


def _extract_score(hit: Any) -> Optional[float]:
    if isinstance(hit, dict):
        score = hit.get("score") or hit.get("similarity")
    else:
        score = getattr(hit, "score", None) or getattr(hit, "similarity", None)
    if score is None:
        return None
    try:
        return float(score)
    except (TypeError, ValueError):
        return None


def search(cfg: LangCacheConfig, prompt: str) -> Optional[dict]:
    """Return cached entry dict or None."""
    try:
        from langcache.models import SearchStrategy  # type: ignore[import-untyped]

        lc = _client(cfg)
        results = lc.search(
            prompt=prompt,
            search_strategies=[SearchStrategy.EXACT, SearchStrategy.SEMANTIC],
            similarity_threshold=cfg.similarity_threshold,
        )
        if not results:
            return None
        hit = results[0] if isinstance(results, list) else results
        response = _extract_response(hit)
        if not response:
            return None
        score = _extract_score(hit)
        match_type = "exact"
        if score is not None and score < 0.999:
            match_type = "semantic"
        return {
            "response": response,
            "match_type": match_type,
            "similarity": score,
        }
    except Exception:  # noqa: BLE001
        return None


def store(cfg: LangCacheConfig, prompt: str, response: str) -> None:
    try:
        lc = _client(cfg)
        lc.set(prompt=prompt, response=response)
    except Exception:  # noqa: BLE001
        pass


__all__ = [
    "DEFAULT_SIMILARITY_THRESHOLD",
    "LangCacheConfig",
    "config_from_env",
    "similarity_threshold",
    "search",
    "store",
]
