"""Thin async client over Redis Context Retriever MCP tools.

Wraps the auto-generated tools exposed by the ``fraud-command-center`` surface
(see ``backend/app/context_models.py``) into a stable, named-method interface
the fraud agent and chatbot can call.

Every public method returns ``(result, TraceRecord)`` so the UI's "Context
Retriever" side-panel can render exactly which tool was called, the inputs,
a short output summary, and latency in milliseconds.

Requires Python 3.11+ and ``redis-context-retriever`` (installed via
``backend/requirements.txt``). The local Python 3.9 dev env does not satisfy
this — tests skip cleanly when the SDK is absent.
"""

from __future__ import annotations

import os
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # SDK requires Python 3.11+; keep import lazy for 3.9 test envs
    from context_surfaces import UnifiedClient


def _load_unified_client():
    """Import the SDK client lazily so this module is importable in environments
    that don't have the SDK installed (e.g. local Python 3.9 unit tests)."""
    from context_surfaces import UnifiedClient as _UC
    return _UC


@dataclass
class TraceRecord:
    """One Context Retriever invocation as the UI panel will render it."""

    tool: str
    input: dict[str, Any]
    output_summary: str
    latency_ms: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _summarise(payload: Any, limit: int = 240) -> str:
    if payload is None:
        return "<no result>"
    if isinstance(payload, list):
        return f"{len(payload)} record(s)"
    if isinstance(payload, dict):
        # MCP tool calls wrap content in {"content": [{"type": "text", "text": "..."}]}.
        content = payload.get("content")
        if isinstance(content, list) and content:
            first = content[0]
            if isinstance(first, dict) and isinstance(first.get("text"), str):
                text = first["text"]
                return text if len(text) <= limit else text[:limit] + "…"
        return f"{len(payload)} field(s)"
    text = str(payload)
    return text if len(text) <= limit else text[:limit] + "…"


class ContextRetriever:
    """Stable, named-method wrapper over the auto-generated MCP tools."""

    def __init__(self, agent_key: str | None = None) -> None:
        self._agent_key = (agent_key or os.environ.get("CTX_AGENT_KEY", "")).strip()
        if not self._agent_key:
            raise RuntimeError("CTX_AGENT_KEY missing — run `make context-up` first.")
        self._client: UnifiedClient | None = None

    async def __aenter__(self) -> "ContextRetriever":
        self._client = _load_unified_client()()
        await self._client.__aenter__()
        return self

    async def __aexit__(self, *exc: object) -> None:
        if self._client is not None:
            await self._client.__aexit__(*exc)
            self._client = None

    async def _call(self, tool: str, args: dict[str, Any]) -> tuple[Any, TraceRecord]:
        client = self._client or _load_unified_client()()
        owns_client = self._client is None
        start = time.perf_counter()
        try:
            result = await client.query_tool(self._agent_key, tool, args)
        finally:
            if owns_client:
                await client.close()
        latency_ms = int((time.perf_counter() - start) * 1000)
        trace = TraceRecord(tool=tool, input=dict(args), output_summary=_summarise(result), latency_ms=latency_ms)
        return result, trace

    async def get_recent_transactions(
        self, customer_id: str, days: int = 30, limit: int = 25
    ) -> tuple[Any, TraceRecord]:
        """Filter the per-customer transaction tool. ``days`` is reported in the
        trace input for the UI but the underlying tool filters by customer_id
        only; the agent then prunes by ``ts`` client-side. Kept the parameter
        so the public method matches the task spec."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        result, trace = await self._call(
            "filter_transaction_by_customer_id",
            {"value": customer_id, "limit": limit},
        )
        trace.input["days"] = days
        trace.input["since"] = cutoff.isoformat()
        return result, trace

    async def find_transactions_by_merchant_category(
        self, customer_id: str, mcc_id: str, limit: int = 25
    ) -> tuple[Any, TraceRecord]:
        """Two-hop: merchants in this category, then customer's transactions
        with any of them. Auto-generated tools are single-field; the agent
        combines on the merchant_id list. Returns the per-merchant filter so
        the agent can fan out."""
        merchants, trace = await self._call(
            "filter_merchant_by_category_code",
            {"value": mcc_id, "limit": limit},
        )
        trace.input["customer_id"] = customer_id
        trace.input["mcc_id"] = mcc_id
        return merchants, trace

    async def devices_seen_for_customer(
        self, customer_id: str, limit: int = 25
    ) -> tuple[Any, TraceRecord]:
        return await self._call(
            "filter_device_by_customer_id",
            {"value": customer_id, "limit": limit},
        )

    async def merchant_reputation(self, merchant_id: str) -> tuple[Any, TraceRecord]:
        return await self._call("get_merchant_by_id", {"id": merchant_id})

    async def search_similar_transactions(
        self, query: str, k: int = 5
    ) -> tuple[Any, TraceRecord]:
        """Surface exposes free-text search per entity. The vector index was
        not enabled at surface creation, so this falls back to text search."""
        return await self._call(
            "search_transaction_by_text",
            {"query": query, "limit": k},
        )
