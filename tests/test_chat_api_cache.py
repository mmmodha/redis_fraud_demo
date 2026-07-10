"""Chat endpoint cache integration tests."""

from __future__ import annotations

import fakeredis
import pytest
from fastapi.testclient import TestClient

from app.agent_tools import Backends
from app.api import deps as api_deps
from app.main import app
from app.stub_agent import StubAgent

from tests.test_stub_agent import FakeContextRetriever, FakePolicyRAG


@pytest.fixture
def client(monkeypatch):
    redis_client = fakeredis.FakeRedis(decode_responses=True)
    agent = StubAgent(Backends(
        redis_client=redis_client,
        ctx=FakeContextRetriever(),
        policy_rag=FakePolicyRAG(),
    ))
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setattr(api_deps, "_redis", lambda: redis_client)

    async def _fake_agent():
        return agent

    monkeypatch.setattr(api_deps, "get_agent", _fake_agent)

    with TestClient(app) as c:
        yield c


def test_chat_naive_rag_cache_hit_on_repeat(client):
    """Naive RAG only hits policy search — no RedisJSON required in fakeredis."""
    body = {"customer_id": "cust_jane", "message": "What is the foreign travel policy?"}
    r1 = client.post("/chat/naive-rag", json=body)
    assert r1.status_code == 200
    assert r1.headers.get("x-cache") == "MISS"
    assert r1.json().get("cached") is False
    assert r1.json().get("input_tokens", 0) > 0

    r2 = client.post("/chat/naive-rag", json=body)
    assert r2.status_code == 200
    assert r2.headers.get("x-cache") == "HIT"
    data = r2.json()
    assert data.get("cached") is True
    assert data.get("tokens_saved_input", 0) > 0
    assert data.get("input_tokens") == 0
