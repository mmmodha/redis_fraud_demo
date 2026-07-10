"""Tests for the chat response cache (LangCache pillar)."""

from __future__ import annotations

import fakeredis
import pytest

from app import chat_cache


@pytest.fixture
def redis_client():
    return fakeredis.FakeRedis(decode_responses=True)


def test_normalize_prompt():
    assert chat_cache.normalize_prompt("  Any upcoming travel?  ") == "any upcoming travel"


def test_semantic_threshold_from_env(monkeypatch):
    monkeypatch.delenv("LANGCACHE_SEMANTIC_THRESHOLD", raising=False)
    assert chat_cache.semantic_threshold() == chat_cache.DEFAULT_SEMANTIC_THRESHOLD
    monkeypatch.setenv("LANGCACHE_SEMANTIC_THRESHOLD", "0.75")
    assert chat_cache.semantic_threshold() == 0.75
    monkeypatch.setenv("LANGCACHE_SEMANTIC_THRESHOLD", "1.5")
    assert chat_cache.semantic_threshold() == 1.0


def test_exact_hit(redis_client):
    payload = {
        "response": {
            "answer": "Singapore trip",
            "trace": {
                "steps": [],
                "total_latency_ms": 100,
                "llm_model": "stub",
            },
        },
        "input_tokens": 820,
        "output_tokens": 180,
    }
    import asyncio
    asyncio.run(chat_cache.put(
        redis_client, "context-surface", "cust_jane",
        "Any upcoming travel?", payload,
        embedder=lambda texts: [[1.0, 0.0, 0.0] for _ in texts],
    ))
    got = asyncio.run(chat_cache.get(
        redis_client, "context-surface", "cust_jane",
        "Any upcoming travel?",
        embedder=lambda texts: [[1.0, 0.0, 0.0] for _ in texts],
    ))
    assert got is not None
    assert got["match_type"] == "exact"
    assert got["response"]["answer"] == "Singapore trip"


def test_clear(redis_client):
    import asyncio
    payload = {"response": {"answer": "x", "trace": {"steps": [], "total_latency_ms": 1, "llm_model": "s"}}}
    asyncio.run(chat_cache.put(
        redis_client, "naive-rag", "cust_mike", "hello", payload,
        embedder=lambda texts: [[0.0, 1.0] for _ in texts],
    ))
    cleared = asyncio.run(chat_cache.clear(redis_client, None))
    assert cleared >= 1
    assert asyncio.run(chat_cache.get(
        redis_client, "naive-rag", "cust_mike", "hello",
        embedder=lambda texts: [[0.0, 1.0] for _ in texts],
    )) is None
