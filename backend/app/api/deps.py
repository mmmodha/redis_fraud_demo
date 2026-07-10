"""Process-wide singletons + dependency-injection helpers for the API layer.

Holds:

* a Redis client (``decode_responses=True``) shared by the Feature Store and
  Agent Memory tool adapters,
* a long-lived ``ContextRetriever`` opened on first request,
* the ``PolicyRAG`` reader (which manages its own binary-mode Redis client).

The singletons are wrapped behind ``get_backends()`` so endpoint handlers and
the (later) Claude agent share one dispatcher instance and one set of
connections.

Everything is created lazily so missing env vars surface as a clean 503
response from the endpoint rather than a startup crash. Secrets (REDIS_URL,
CTX_AGENT_KEY) are never logged or echoed.
"""

from __future__ import annotations

import os
from typing import Optional

import redis

from app.agent_tools import Backends
from app.claude_agent import ClaudeAgent
from app.context_retriever import ContextRetriever
from app.mock_claude import MockClaudeClient
from app.policy_rag import PolicyRAG
from app.stub_agent import StubAgent

# Agent surface seen by the HTTP layer. All three implementations expose the
# same coroutines (``score``, ``chat_context_surface``, ``chat_naive_rag``),
# so FastAPI only ever holds onto one of them at a time.
Agent = StubAgent | ClaudeAgent | MockClaudeClient


_redis_client: Optional[redis.Redis] = None
_ctx: Optional[ContextRetriever] = None
_rag: Optional[PolicyRAG] = None
_backends: Optional[Backends] = None
_agent: Optional[Agent] = None


def _redis() -> redis.Redis:
    global _redis_client
    if _redis_client is None:
        url = os.environ.get("REDIS_URL", "").strip()
        if not url:
            raise RuntimeError("REDIS_URL is not set")
        _redis_client = redis.Redis.from_url(
            url, decode_responses=True,
            socket_timeout=5, socket_connect_timeout=5,
        )
    return _redis_client


def _context_retriever() -> ContextRetriever:
    global _ctx
    if _ctx is None:
        _ctx = ContextRetriever()
    return _ctx


def _policy_rag() -> PolicyRAG:
    global _rag
    if _rag is None:
        _rag = PolicyRAG.from_env()
    return _rag


async def get_backends() -> Backends:
    """Build/return the shared backends bag. Opens the Context Retriever
    MCP session on first call when ``CTX_AGENT_KEY`` is configured —
    otherwise the bag is built with ``ctx=None`` so the rest of the stack
    still runs (tools that need CR raise a clean error if invoked, while
    the mock-Claude path never invokes any tool at all)."""
    global _backends, _ctx
    if _backends is None:
        ctx: Optional[ContextRetriever] = None
        if (os.environ.get("CTX_AGENT_KEY") or "").strip():
            ctx = _context_retriever()
            # ContextRetriever opens its UnifiedClient lazily on first __aenter__;
            # call it once here so subsequent tool calls reuse the connection.
            await ctx.__aenter__()
        _backends = Backends(
            redis_client=_redis(),
            ctx=ctx,
            policy_rag=_policy_rag(),
        )
    return _backends


def _resolve_agent_mode() -> str:
    """Decide which agent implementation backs the endpoints.

    Precedence:
      1. Explicit ``AGENT_MODE`` env var: ``claude`` / ``stub`` / ``mock``.
      2. ``claude`` if ``ANTHROPIC_API_KEY`` is present, else ``mock``.

    ``stub`` is preserved (deterministic real-tool agent) so existing
    tests that wire fakeredis + a fake Context Retriever keep working;
    the default no-key path now lands on ``mock`` so the trace UI gets
    canned SSE events rather than skipping tool dispatch errors.
    """
    mode = (os.environ.get("AGENT_MODE") or "").strip().lower()
    if mode in ("stub", "claude", "mock"):
        return mode
    if (os.environ.get("ANTHROPIC_API_KEY") or "").strip():
        return "claude"
    return "mock"


async def get_agent() -> Agent:
    global _agent
    if _agent is None:
        backends = await get_backends()
        mode = _resolve_agent_mode()
        if mode == "claude":
            _agent = ClaudeAgent(backends)
        elif mode == "stub":
            _agent = StubAgent(backends)
        else:
            _agent = MockClaudeClient(backends)
    return _agent


async def shutdown() -> None:
    """Close the Context Retriever session at app shutdown."""
    global _ctx, _backends, _agent
    if _ctx is not None:
        try:
            await _ctx.__aexit__(None, None, None)
        except Exception:  # noqa: BLE001
            pass
        _ctx = None
    _backends = None
    _agent = None


__all__ = ["Agent", "get_backends", "get_agent", "shutdown", "_redis"]
