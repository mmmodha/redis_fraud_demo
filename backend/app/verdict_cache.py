"""Verdict cache — second-run-instant playback of hero scenarios (Wave 7n).

After the first run of a hero (~30s real agent trace + analyst summary),
the full ScoreResponse plus the captured stream events are written into
Redis under ``cache:agent:verdict:{customer_id}:{tx_signature}``. Any
subsequent run of the same hero serves from cache: the non-streaming
endpoint returns in single-digit ms, and the streaming endpoint replays
the captured events with a 5ms gap so the trace strip still flickers
visibly in ~50ms total wall-clock.

This is the LangCache pillar made literal — same input → same decision →
served from Redis.

The redis client passed in is the shared ``decode_responses=True`` client
from :mod:`app.api.deps`; the get/put/clear helpers are ``async`` but the
underlying Redis ops are synchronous and run via ``asyncio.to_thread``.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
from typing import Any, Optional


KEY_PREFIX = "cache:agent:verdict"
INDEX_KEY = f"{KEY_PREFIX}:index"  # Redis SET of every live cache key.
DEFAULT_TTL_SECONDS = 86400  # 24h — TTL is mandatory on every write.


def transaction_signature(transaction: Any) -> str:
    """Stable 12-char hex signature for a TransactionPayload-ish object.

    Hashes the demo-relevant fields (amount, merchant_id, country, device_id,
    currency) so two runs of the same hero scenario collide. ``None`` for a
    field stringifies as ``"None"`` which is fine — same hero → same fields →
    same hash.
    """
    if transaction is None:
        payload_str = ""
    else:
        if hasattr(transaction, "model_dump"):
            d = transaction.model_dump()
        elif isinstance(transaction, dict):
            d = transaction
        else:
            d = {}
        parts = [
            f"a={d.get('amount')}",
            f"u={d.get('currency')}",
            f"m={d.get('merchant_id')}",
            f"c={d.get('country')}",
            f"d={d.get('device_id')}",
        ]
        payload_str = "|".join(parts)
    return hashlib.sha1(payload_str.encode("utf-8")).hexdigest()[:12]


def _key(customer_id: str, tx_signature: str) -> str:
    return f"{KEY_PREFIX}:{customer_id}:{tx_signature}"


def _customer_index_key(customer_id: str) -> str:
    return f"{INDEX_KEY}:{customer_id}"


async def get(
    redis_client: Any, customer_id: str, tx_signature: str,
) -> Optional[dict]:
    """Return the cached payload dict or None on miss / decode error."""
    if redis_client is None:
        return None
    raw = await asyncio.to_thread(redis_client.get, _key(customer_id, tx_signature))
    if not raw:
        return None
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError, ValueError):
        return None


async def put(
    redis_client: Any,
    customer_id: str,
    tx_signature: str,
    payload: dict,
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
) -> None:
    """Write the payload with a TTL — never an unbounded key.

    Also indexes the key in two Redis SETs (global + per-customer) so
    :func:`clear` is O(cached-entries) instead of SCANning the whole DB.
    """
    if redis_client is None:
        return
    raw = json.dumps(payload, separators=(",", ":"))
    key = _key(customer_id, tx_signature)
    cust_idx = _customer_index_key(customer_id)

    def _write() -> None:
        pipe = redis_client.pipeline()
        pipe.set(key, raw, ex=ttl_seconds)
        pipe.sadd(INDEX_KEY, key)
        pipe.sadd(cust_idx, key)
        pipe.execute()

    await asyncio.to_thread(_write)


async def clear(redis_client: Any, customer_id: Optional[str] = None) -> int:
    """Clear cache entries using the index SET (no SCAN, no KEYS).

    ``customer_id=None`` clears every verdict cache key under the prefix.
    Returns the number of deleted cache entries (index/bookkeeping deletes
    are not counted). Stale index entries whose underlying key has already
    expired are tolerated — ``DEL`` of a missing key is a no-op in Redis.
    """
    if redis_client is None:
        return 0

    def _clear_for_customer(cid: str) -> int:
        cust_idx = _customer_index_key(cid)
        members = list(redis_client.smembers(cust_idx))
        cleared = 0
        if members:
            cleared = redis_client.delete(*members)
            redis_client.srem(INDEX_KEY, *members)
        redis_client.delete(cust_idx)
        return cleared

    def _clear_all() -> int:
        members = list(redis_client.smembers(INDEX_KEY))
        cleared = 0
        if members:
            cleared = redis_client.delete(*members)
        # Tear down every per-customer index referenced by the global set,
        # plus the global set itself. Derived from member key names —
        # format ``cache:agent:verdict:{customer_id}:{tx_signature}``.
        index_keys = {INDEX_KEY}
        for k in members:
            parts = k.split(":")
            if len(parts) >= 5:
                index_keys.add(_customer_index_key(parts[3]))
        redis_client.delete(*index_keys)
        return cleared

    if customer_id:
        return await asyncio.to_thread(_clear_for_customer, customer_id)
    return await asyncio.to_thread(_clear_all)


__all__ = [
    "DEFAULT_TTL_SECONDS",
    "KEY_PREFIX",
    "INDEX_KEY",
    "transaction_signature",
    "get",
    "put",
    "clear",
]
