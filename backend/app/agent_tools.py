"""Claude-tool-schema-ready adapter layer over the four IRIS components.

Every capability the fraud agent / chatbot can call is described once here:

  ``AGENT_TOOL_SCHEMAS``  → ``list[{name, description, input_schema}]``
      Drop directly into ``client.messages.create(tools=...)`` in Wave 3b.

  ``async call_tool(name, arguments, *, backends) -> (output, TraceStep)``
      Dispatcher: routes the tool name to the right adapter, returns the
      tool's output payload alongside a frozen-schema ``TraceStep`` for the
      UI side panels.

The dispatcher is the **only** way the stub agent and (later) the Claude
agent interact with the IRIS layers — keep it stable.

``Backends`` is a small bag of injected clients so unit tests can pass
fakes (fakeredis for feature_store/agent_memory, a stub for the Context
Retriever, an in-memory PolicyRAG) without touching the real surfaces.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any, Awaitable, Callable, Optional

import redis

from app import agent_memory as am
from app import features as feature_store
from app.schemas import TraceStep

if TYPE_CHECKING:  # avoid hard dep on Python 3.11+ SDK at import time
    from app.context_retriever import ContextRetriever
    from app.policy_rag import PolicyRAG


# ---------- backend container ---------------------------------------------

@dataclass
class Backends:
    """Injected dependencies for ``call_tool``.

    Any field may be left ``None`` if the calling code knows it will not
    invoke tools that need it. The dispatcher raises a clear error if a
    required backend is missing for the requested tool, rather than
    crashing on AttributeError half-way through.
    """

    redis_client: Optional[redis.Redis] = None
    ctx: Optional[ContextRetriever] = None
    policy_rag: Optional[PolicyRAG] = None


# ---------- tool schemas (Claude-ready) -----------------------------------

AGENT_TOOL_SCHEMAS: list[dict[str, Any]] = [
    # --- Context Retriever -------------------------------------------------
    {
        "name": "get_customer_context",
        "description": (
            "Look up a customer's profile (name, home country/city, account "
            "creation date) from the Redis Context Retriever surface."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "customer_id": {"type": "string", "description": "e.g. cust_jane"},
            },
            "required": ["customer_id"],
        },
    },
    {
        "name": "get_recent_transactions",
        "description": (
            "Most recent transactions for a customer (across all their cards), "
            "newest first. ``days`` filters the lookback window."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "customer_id": {"type": "string"},
                "days": {"type": "integer", "default": 30, "minimum": 1, "maximum": 365},
                "limit": {"type": "integer", "default": 25, "minimum": 1, "maximum": 100},
            },
            "required": ["customer_id"],
        },
    },
    {
        "name": "find_similar_fraud",
        "description": (
            "Find historical transactions whose text representation resembles "
            "the provided query (free-text vector / text search). Useful for "
            "‘has this pattern been seen as fraud before?’."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "k": {"type": "integer", "default": 5, "minimum": 1, "maximum": 20},
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_merchant_reputation",
        "description": "Fetch a merchant record (name, category, country, risk flags) by merchant_id.",
        "input_schema": {
            "type": "object",
            "properties": {"merchant_id": {"type": "string"}},
            "required": ["merchant_id"],
        },
    },
    {
        "name": "get_devices_for_customer",
        "description": "List devices Redis has ever seen for this customer (id, fingerprint, country, first/last seen).",
        "input_schema": {
            "type": "object",
            "properties": {
                "customer_id": {"type": "string"},
                "limit": {"type": "integer", "default": 25, "minimum": 1, "maximum": 100},
            },
            "required": ["customer_id"],
        },
    },
    {
        "name": "get_disputes",
        "description": (
            "List dispute records Redis has on file for this customer over the "
            "last ``days`` window. Empty list means the customer has a clean "
            "dispute record. Each item carries dispute_id, transaction_id, "
            "merchant_name, amount, currency, opened_at, status, outcome, reason."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "customer_id": {"type": "string"},
                "days": {"type": "integer", "default": 180, "minimum": 1, "maximum": 730},
            },
            "required": ["customer_id"],
        },
    },
    {
        "name": "get_pending_review",
        "description": (
            "The in-flight transaction currently queued at the agent's review "
            "door for this customer, plus its risk markers. Returns ``null`` "
            "when no review is pending. Shape: transaction_id, amount, "
            "currency, merchant_name, merchant_country, merchant_category, "
            "device_id, device_first_seen_today, foreign_country, "
            "impossible_travel, occurred_at."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "customer_id": {"type": "string"},
            },
            "required": ["customer_id"],
        },
    },

    # --- Feature Store -----------------------------------------------------
    {
        "name": "get_velocity_features",
        "description": "Real-time velocity counters for a card (1h / 24h / 7d) plus amount stats.",
        "input_schema": {
            "type": "object",
            "properties": {"card_id": {"type": "string"}},
            "required": ["card_id"],
        },
    },
    {
        "name": "get_geo_entropy",
        "description": (
            "Recent geographic dispersion score (0–1) for a customer's spending; "
            "high values flag unusual cross-country activity."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "customer_id": {"type": "string"},
                "card_id": {"type": "string", "description": "Optional override; defaults to the customer's primary card."},
            },
            "required": ["customer_id"],
        },
    },
    {
        "name": "get_new_device_flag",
        "description": "Has this device been seen on this customer's card in the last 24 hours? Returns a boolean flag + first-seen timestamp.",
        "input_schema": {
            "type": "object",
            "properties": {
                "customer_id": {"type": "string"},
                "device_id": {"type": "string"},
                "card_id": {"type": "string", "description": "Optional override; defaults to the customer's primary card."},
            },
            "required": ["customer_id", "device_id"],
        },
    },

    # --- Agent Memory ------------------------------------------------------
    {
        "name": "get_customer_memory",
        "description": (
            "Per-customer Agent Memory: declared travel windows, prior disputes, "
            "flagged devices, and prior chatbot conversation notes."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"customer_id": {"type": "string"}},
            "required": ["customer_id"],
        },
    },
    {
        "name": "append_conversation_note",
        "description": "Persist a short note about this customer to Agent Memory (for use in future turns).",
        "input_schema": {
            "type": "object",
            "properties": {
                "customer_id": {"type": "string"},
                "note": {"type": "string"},
                "source": {"type": "string", "default": "agent"},
            },
            "required": ["customer_id", "note"],
        },
    },

    # --- Policy RAG --------------------------------------------------------
    {
        "name": "search_policy",
        "description": (
            "Vector-search the bank's policy and study corpus (fraud SOPs, "
            "regulatory summaries, segment guides). Returns the top-k chunks "
            "ranked by cosine similarity. Used by BOTH the IRIS pipeline and "
            "the naive-RAG pipeline."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "k": {"type": "integer", "default": 5, "minimum": 1, "maximum": 20},
            },
            "required": ["query"],
        },
    },
]


# ---------- helpers -------------------------------------------------------

# Heroes whose customer→primary-card mapping is hard-coded in data/heroes.py.
# Outside that set we look up the customer's card lazily from Redis. Keeping
# this small mapping inline avoids importing data.heroes in production paths
# (data/* depends on psycopg + a Postgres connection).
_HERO_CARD: dict[str, str] = {
    "cust_mike": "card_mike_visa",
    "cust_jane": "card_jane_visa",
    "cust_alex": "card_alex_visa",
}


def _resolve_card_id(backends: Backends, customer_id: str, override: Optional[str]) -> str:
    """Return ``override`` if given, else the hero map, else raise."""
    if override:
        return override
    card = _HERO_CARD.get(customer_id)
    if card:
        return card
    raise ValueError(
        f"unable to resolve a card_id for customer_id={customer_id!r}; "
        "pass card_id explicitly"
    )


def _need(backend: Any, name: str, tool: str) -> Any:
    if backend is None:
        raise RuntimeError(f"tool {tool!r} requires backend {name!r} but it was not provided")
    return backend


def _trace(
    component: str, tool: str, inp: dict[str, Any],
    summary: str, data: Optional[dict[str, Any]],
    latency_ms: int, keys: list[str],
) -> TraceStep:
    return TraceStep(
        component=component, tool=tool, input=dict(inp),
        output_summary=summary, output_data=data,
        latency_ms=latency_ms, redis_keys_touched=keys,
    )


def _ctx_payload(result: Any) -> dict[str, Any]:
    """Wrap a context-retriever return into a JSON-safe dict for the trace."""
    if result is None:
        return {"result": None}
    if isinstance(result, dict):
        return result
    if isinstance(result, list):
        return {"items": result, "count": len(result)}
    return {"value": result}


# ---------- adapters ------------------------------------------------------

async def _ctx_call(backends: Backends, tool: str, method: str, **kwargs: Any) -> tuple[Any, TraceStep]:
    ctx: ContextRetriever = _need(backends.ctx, "ctx", tool)
    fn: Callable[..., Awaitable] = getattr(ctx, method)
    result, ctx_trace = await fn(**kwargs)
    return result, _trace(
        component="context_retriever",
        tool=tool,
        inp=dict(ctx_trace.input),
        summary=ctx_trace.output_summary,
        data=_ctx_payload(result),
        latency_ms=ctx_trace.latency_ms,
        keys=[],
    )


async def _get_customer_context(backends: Backends, args: dict) -> tuple[Any, TraceStep]:
    # The Context Retriever exposes customers as the primary-key GET tool
    # ``get_customer_by_id`` (auto-generated from the Customer schema).
    ctx: ContextRetriever = _need(backends.ctx, "ctx", "get_customer_context")
    customer_id = args["customer_id"]
    result, ctx_trace = await ctx._call(  # noqa: SLF001
        "get_customer_by_id",
        {"id": customer_id},
    )
    trace = _trace(
        component="context_retriever",
        tool="get_customer_context",
        inp={"customer_id": customer_id},
        summary=ctx_trace.output_summary,
        data=_ctx_payload(result),
        latency_ms=ctx_trace.latency_ms,
        keys=[f"customer:{customer_id}"],
    )
    return result, trace


async def _get_recent_transactions(backends: Backends, args: dict) -> tuple[Any, TraceStep]:
    result, step = await _ctx_call(
        backends, "get_recent_transactions", "get_recent_transactions",
        customer_id=args["customer_id"],
        days=int(args.get("days", 30)),
        limit=int(args.get("limit", 25)),
    )
    return result, step


async def _find_similar_fraud(backends: Backends, args: dict) -> tuple[Any, TraceStep]:
    result, step = await _ctx_call(
        backends, "find_similar_fraud", "search_similar_transactions",
        query=args["query"], k=int(args.get("k", 5)),
    )
    return result, step


async def _get_merchant_reputation(backends: Backends, args: dict) -> tuple[Any, TraceStep]:
    result, step = await _ctx_call(
        backends, "get_merchant_reputation", "merchant_reputation",
        merchant_id=args["merchant_id"],
    )
    step.redis_keys_touched = [f"merchant:{args['merchant_id']}"]
    return result, step


async def _get_devices_for_customer(backends: Backends, args: dict) -> tuple[Any, TraceStep]:
    result, step = await _ctx_call(
        backends, "get_devices_for_customer", "devices_seen_for_customer",
        customer_id=args["customer_id"],
        limit=int(args.get("limit", 25)),
    )
    return result, step


def _disputes_key(customer_id: str) -> str:
    return f"disputes:{customer_id}"


def _pending_review_key(customer_id: str) -> str:
    return f"pending_review:{customer_id}"


def _within_days(opened_at: Any, cutoff_iso: str) -> bool:
    if not isinstance(opened_at, str):
        return True
    return opened_at >= cutoff_iso


async def _get_disputes(backends: Backends, args: dict) -> tuple[Any, TraceStep]:
    # Reads the per-customer dispute list directly from Redis (key
    # ``disputes:{customer_id}``). Tagged as context_retriever because it
    # serves the same "look up entity context" role as the other CR tools.
    client: redis.Redis = _need(backends.redis_client, "redis_client", "get_disputes")
    customer_id = args["customer_id"]
    days = int(args.get("days", 180))
    key = _disputes_key(customer_id)
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    start = time.perf_counter()
    raw = client.json().get(key, "$")
    latency_ms = int((time.perf_counter() - start) * 1000)
    doc: dict[str, Any]
    if not raw:
        doc = {"customer_id": customer_id, "items": []}
    else:
        first = raw[0] if isinstance(raw, list) else raw
        if isinstance(first, list):
            doc = {"customer_id": customer_id, "items": first}
        elif isinstance(first, dict):
            doc = first
        else:
            doc = {"customer_id": customer_id, "items": []}
    items = doc.get("items") or []
    filtered = [d for d in items if _within_days(d.get("opened_at"), cutoff)]
    out = {
        "customer_id": customer_id,
        "days": days,
        "items": filtered,
        "count": len(filtered),
    }
    summary = f"{len(filtered)} dispute(s) in last {days}d"
    return out, _trace(
        component="context_retriever", tool="get_disputes",
        inp={"customer_id": customer_id, "days": days},
        summary=summary, data=out,
        latency_ms=latency_ms, keys=[key],
    )


def _read_pending_review(client: redis.Redis, customer_id: str) -> Optional[dict[str, Any]]:
    return feature_store.read_pending_review(client, customer_id)


async def _get_pending_review(backends: Backends, args: dict) -> tuple[Any, TraceStep]:
    # Reads ``pending_review:{customer_id}`` JSON staging record. Returns
    # ``null`` when no transaction is currently queued for review.
    client: redis.Redis = _need(backends.redis_client, "redis_client", "get_pending_review")
    customer_id = args["customer_id"]
    key = _pending_review_key(customer_id)
    start = time.perf_counter()
    raw = client.json().get(key, "$")
    latency_ms = int((time.perf_counter() - start) * 1000)
    payload: Any = None
    if raw:
        payload = raw[0] if isinstance(raw, list) else raw
    if payload is None:
        summary = "no pending review"
        data = {"customer_id": customer_id, "pending": None}
    else:
        summary = (
            f"pending {payload.get('amount')} {payload.get('currency')} "
            f"at {payload.get('merchant_name')} ({payload.get('merchant_country')})"
        )
        data = payload
    return payload, _trace(
        component="context_retriever", tool="get_pending_review",
        inp={"customer_id": customer_id},
        summary=summary, data=data,
        latency_ms=latency_ms, keys=[key],
    )


async def _get_velocity_features(backends: Backends, args: dict) -> tuple[Any, TraceStep]:
    client: redis.Redis = _need(backends.redis_client, "redis_client", "get_velocity_features")
    card_id = args["card_id"]
    store = feature_store.FeatureStore(client)
    start = time.perf_counter()
    data = store.get_features(card_id)
    latency_ms = int((time.perf_counter() - start) * 1000)
    velocity = {k: data.get(k, 0) for k in
                ("velocity_1h", "velocity_24h", "velocity_7d",
                 "amount_avg_30d", "amount_max_24h")}
    summary = (
        f"v1h={velocity['velocity_1h']} v24h={velocity['velocity_24h']} "
        f"v7d={velocity['velocity_7d']} avg30d={velocity['amount_avg_30d']:.2f}"
    )
    return data, _trace(
        component="feature_store", tool="get_velocity_features",
        inp={"card_id": card_id},
        summary=summary, data=data,
        latency_ms=latency_ms,
        keys=[feature_store.feat_key(card_id)],
    )


async def _get_geo_entropy(backends: Backends, args: dict) -> tuple[Any, TraceStep]:
    client: redis.Redis = _need(backends.redis_client, "redis_client", "get_geo_entropy")
    customer_id = args["customer_id"]
    card_id = _resolve_card_id(backends, customer_id, args.get("card_id"))
    start = time.perf_counter()
    data = feature_store.get_features(card_id, customer_id=customer_id)
    latency_ms = int((time.perf_counter() - start) * 1000)
    entropy = float(data.get("geo_entropy", 0.0) or 0.0)
    impossible_travel = bool(data.get("impossible_travel"))
    out = {
        "customer_id": customer_id,
        "card_id": card_id,
        "geo_entropy": entropy,
        "impossible_travel": impossible_travel,
    }
    summary = f"geo_entropy={entropy:.3f}"
    if impossible_travel:
        summary += " — impossible-travel pattern"
    return out, _trace(
        component="feature_store", tool="get_geo_entropy",
        inp={"customer_id": customer_id, "card_id": card_id},
        summary=summary,
        data=out,
        latency_ms=latency_ms,
        keys=[feature_store.feat_key(card_id), _pending_review_key(customer_id)],
    )


async def _get_new_device_flag(backends: Backends, args: dict) -> tuple[Any, TraceStep]:
    client: redis.Redis = _need(backends.redis_client, "redis_client", "get_new_device_flag")
    customer_id = args["customer_id"]
    device_id = args["device_id"]
    card_id = _resolve_card_id(backends, customer_id, args.get("card_id"))
    start = time.perf_counter()
    data = feature_store.get_features(card_id, customer_id=customer_id)
    # The feature worker writes a 24h "new device" boolean (0/1) per card,
    # plus a side hash feat:_dev:{card_id} containing first_seen_ts per device.
    new_24h = int(data.get("new_device_24h", 0) or 0)
    dev_key = f"feat:_dev:{card_id}"
    first_seen = client.hget(dev_key, device_id)
    if isinstance(first_seen, bytes):
        first_seen = first_seen.decode("utf-8", errors="replace")
    latency_ms = int((time.perf_counter() - start) * 1000)
    out = {
        "customer_id": customer_id, "card_id": card_id, "device_id": device_id,
        "new_device_24h": bool(new_24h),
        "device_first_seen_ts": first_seen,
        "device_known_to_card": first_seen is not None,
    }
    summary = (
        f"new_device_24h={bool(new_24h)} "
        f"first_seen={'never' if first_seen is None else first_seen}"
    )
    return out, _trace(
        component="feature_store", tool="get_new_device_flag",
        inp={"customer_id": customer_id, "device_id": device_id, "card_id": card_id},
        summary=summary, data=out,
        latency_ms=latency_ms,
        keys=[feature_store.feat_key(card_id), dev_key],
    )


async def _get_customer_memory(backends: Backends, args: dict) -> tuple[Any, TraceStep]:
    client: redis.Redis = _need(backends.redis_client, "redis_client", "get_customer_memory")
    customer_id = args["customer_id"]
    start = time.perf_counter()
    doc = am.get_memory(client, customer_id)
    latency_ms = int((time.perf_counter() - start) * 1000)
    travel = doc.get("travel_windows") or []
    notes = doc.get("conversation_notes") or []
    summary = f"travel_windows={len(travel)} notes={len(notes)}"
    return doc, _trace(
        component="agent_memory", tool="get_customer_memory",
        inp={"customer_id": customer_id},
        summary=summary, data=doc,
        latency_ms=latency_ms,
        keys=[f"mem:{customer_id}"],
    )


async def _append_conversation_note(backends: Backends, args: dict) -> tuple[Any, TraceStep]:
    client: redis.Redis = _need(backends.redis_client, "redis_client", "append_conversation_note")
    customer_id = args["customer_id"]
    note = args["note"]
    source = args.get("source", "agent")
    start = time.perf_counter()
    am.append_conversation_note(client, customer_id, note, source=source)
    latency_ms = int((time.perf_counter() - start) * 1000)
    out = {"customer_id": customer_id, "appended": True}
    return out, _trace(
        component="agent_memory", tool="append_conversation_note",
        inp={"customer_id": customer_id, "note": note, "source": source},
        summary=f"appended note ({len(note)} chars)", data=out,
        latency_ms=latency_ms, keys=[f"mem:{customer_id}"],
    )


async def _search_policy(backends: Backends, args: dict) -> tuple[Any, TraceStep]:
    rag: PolicyRAG = _need(backends.policy_rag, "policy_rag", "search_policy")
    query = args["query"]
    k = int(args.get("k", 5))
    chunks, step = rag.search(query, k=k)
    # PolicyRAG.search already returns a TraceStep; just return it.
    return chunks, step


# ---------- dispatcher ----------------------------------------------------

_DISPATCH: dict[str, Callable[[Backends, dict], Awaitable[tuple[Any, TraceStep]]]] = {
    "get_customer_context": _get_customer_context,
    "get_recent_transactions": _get_recent_transactions,
    "find_similar_fraud": _find_similar_fraud,
    "get_merchant_reputation": _get_merchant_reputation,
    "get_devices_for_customer": _get_devices_for_customer,
    "get_disputes": _get_disputes,
    "get_pending_review": _get_pending_review,
    "get_velocity_features": _get_velocity_features,
    "get_geo_entropy": _get_geo_entropy,
    "get_new_device_flag": _get_new_device_flag,
    "get_customer_memory": _get_customer_memory,
    "append_conversation_note": _append_conversation_note,
    "search_policy": _search_policy,
}


async def call_tool(
    name: str,
    arguments: dict[str, Any],
    *,
    backends: Backends,
) -> tuple[Any, TraceStep]:
    """Look up and invoke a single tool by name.

    Returns ``(output_payload, trace_step)``. The output payload is what the
    Wave 3b Claude integration will hand back to the model as the tool result.
    The trace step goes onto the ``AgentTrace`` the UI consumes.
    """
    fn = _DISPATCH.get(name)
    if fn is None:
        raise KeyError(f"unknown tool: {name!r} (known: {sorted(_DISPATCH)})")
    return await fn(backends, arguments)


# Sanity check: the dispatcher and schemas must agree on the tool set.
_schema_names = {t["name"] for t in AGENT_TOOL_SCHEMAS}
_dispatch_names = set(_DISPATCH)
assert _schema_names == _dispatch_names, (
    "AGENT_TOOL_SCHEMAS / _DISPATCH out of sync: "
    f"only-in-schemas={_schema_names - _dispatch_names}, "
    f"only-in-dispatch={_dispatch_names - _schema_names}"
)


__all__ = ["AGENT_TOOL_SCHEMAS", "Backends", "call_tool"]
