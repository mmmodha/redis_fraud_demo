"""Stream consumer that keeps ``feat:{card_id}`` hashes fresh.

Reads ``stream:transactions`` with a consumer group so multiple workers can
share the load and any worker can resume after a restart. Per transaction it:

  1. Appends the tx to ``feat:_hist:{card_id}`` (sorted set, score=ts).
  2. Records first-seen of the device in ``feat:_dev:{card_id}`` (hash).
  3. Recomputes the feature hash and HSETs ``feat:{card_id}``.

mcc is looked up via ``JSON.GET merchant:{id} $.category_code`` so RDI's
merchant docs feed the merchant-category histogram. Inline ``merchant_category``
in the event is honoured first (useful for tests / direct producers).
"""

from __future__ import annotations

import json
import math
import os
import signal
import sys
import time
from collections import Counter
from datetime import datetime
from typing import Any, Optional

import redis
from redis.exceptions import ResponseError


STREAM_KEY = "stream:transactions"
GROUP_NAME = "feature-store"
CONSUMER_NAME = os.environ.get("FEATURE_CONSUMER_NAME") or f"fw-{os.getpid()}"

WINDOW_30D = 30 * 86400
WINDOW_7D = 7 * 86400
WINDOW_24H = 24 * 3600
WINDOW_1H = 3600


def hist_key(card_id: str) -> str:
    return f"feat:_hist:{card_id}"


def dev_key(card_id: str) -> str:
    return f"feat:_dev:{card_id}"


def feat_key(card_id: str) -> str:
    return f"feat:{card_id}"


def parse_ts(value: Any) -> float:
    if value is None or value == "":
        return time.time()
    if isinstance(value, (int, float)):
        v = float(value)
        return v / 1000.0 if v > 1e12 else v
    s = str(value)
    try:
        v = float(s)
        return v / 1000.0 if v > 1e12 else v
    except ValueError:
        pass
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return time.time()


def shannon_entropy_normalized(values: list[str]) -> float:
    """Shannon entropy of the country distribution, normalized to [0, 1]."""
    if len(values) < 2:
        return 0.0
    counts = Counter(values)
    if len(counts) < 2:
        return 0.0
    total = sum(counts.values())
    h = -sum((c / total) * math.log(c / total) for c in counts.values())
    return h / math.log(len(counts))


def _fetch_mcc(r: redis.Redis, tx: dict) -> str:
    inline = tx.get("merchant_category") or tx.get("mcc")
    if inline:
        return str(inline)
    merchant_id = tx.get("merchant_id")
    if not merchant_id:
        return ""
    try:
        raw = r.execute_command("JSON.GET", f"merchant:{merchant_id}", "$.category_code")
    except (ResponseError, redis.ConnectionError):
        return ""
    if not raw:
        return ""
    try:
        parsed = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return ""
    if isinstance(parsed, list):
        return str(parsed[0]) if parsed else ""
    return str(parsed)


def update_for_transaction(r: redis.Redis, tx: dict) -> Optional[str]:
    """Apply one transaction event to the feature hash for its card.

    Returns the card_id that was updated, or None if the event lacks one.
    """
    card_id = tx.get("card_id")
    if not card_id:
        return None
    ts = parse_ts(tx.get("ts") or tx.get("timestamp"))
    try:
        amount = float(tx.get("amount") or 0)
    except (TypeError, ValueError):
        amount = 0.0
    country = (tx.get("country") or "").strip()
    device_id = tx.get("device_id") or ""
    tx_id = tx.get("transaction_id") or tx.get("tx_id") or f"tx_{ts}"
    mcc = _fetch_mcc(r, tx)

    member = json.dumps(
        {"tx_id": tx_id, "amount": amount, "country": country, "mcc": mcc, "device_id": device_id},
        separators=(",", ":"),
    )

    h_key = hist_key(card_id)
    d_key = dev_key(card_id)
    cutoff = ts - WINDOW_30D

    pipe = r.pipeline()
    pipe.zadd(h_key, {member: ts})
    pipe.zremrangebyscore(h_key, "-inf", cutoff)
    if device_id:
        pipe.hsetnx(d_key, device_id, ts)
        pipe.hget(d_key, device_id)
    else:
        pipe.echo("noop")
        pipe.echo("")
    pipe.zrangebyscore(h_key, cutoff, "+inf", withscores=True)
    pipe.expire(h_key, WINDOW_30D * 2)
    pipe.expire(d_key, WINDOW_30D * 2)
    res = pipe.execute()

    first_seen_raw = res[3] if device_id else None
    first_seen = parse_ts(first_seen_raw) if first_seen_raw else ts
    entries_raw = res[4]

    entries: list[tuple[dict, float]] = []
    for raw_member, score in entries_raw:
        try:
            data = json.loads(raw_member)
        except (TypeError, json.JSONDecodeError):
            continue
        entries.append((data, float(score)))

    # Velocity counts use the transaction's event time, not its ingest time:
    # bound by ``s <= ts`` so out-of-order ingest of historical events does not
    # let "future" rows leak into the rolling window of an older one.
    count_1h = sum(1 for _, s in entries if ts - WINDOW_1H <= s <= ts)
    count_24h = sum(1 for _, s in entries if ts - WINDOW_24H <= s <= ts)
    count_7d = sum(1 for _, s in entries if ts - WINDOW_7D <= s <= ts)

    amounts_30d = [float(e["amount"]) for e, _ in entries]
    avg_30d = sum(amounts_30d) / len(amounts_30d) if amounts_30d else 0.0
    max_24h = max(
        (float(e["amount"]) for e, s in entries if ts - WINDOW_24H <= s <= ts),
        default=0.0,
    )

    countries_30d = [e["country"] for e, _ in entries if e["country"]]
    geo_ent = shannon_entropy_normalized(countries_30d)

    mccs = [e["mcc"] for e, _ in entries if e["mcc"]]
    top3 = ",".join(m for m, _ in Counter(mccs).most_common(3))

    new_dev = 1 if device_id and (ts - first_seen) < WINDOW_24H else 0

    r.hset(feat_key(card_id), mapping={
        "velocity_1h": count_1h,
        "velocity_24h": count_24h,
        "velocity_7d": count_7d,
        "amount_avg_30d": f"{avg_30d:.2f}",
        "amount_max_24h": f"{max_24h:.2f}",
        "geo_entropy": f"{geo_ent:.4f}",
        "mcc_top_3": top3,
        "new_device_24h": new_dev,
        "last_updated_at": f"{ts:.3f}",
    })
    return card_id


def ensure_group(r: redis.Redis) -> None:
    try:
        r.xgroup_create(STREAM_KEY, GROUP_NAME, id="0", mkstream=True)
    except ResponseError as exc:
        if "BUSYGROUP" not in str(exc):
            raise


def process_once(
    r: redis.Redis,
    *,
    count: int = 32,
    block_ms: Optional[int] = 5000,
    consumer: str = CONSUMER_NAME,
) -> int:
    """Pull one batch and apply it. Returns the number of acked events.

    ``block_ms=None`` makes the read non-blocking (useful for tests / drain
    loops). A positive integer blocks for that many milliseconds.
    """
    resp = r.xreadgroup(GROUP_NAME, consumer, {STREAM_KEY: ">"}, count=count, block=block_ms)
    if not resp:
        return 0
    processed = 0
    for _stream, entries in resp:
        for entry_id, fields in entries:
            try:
                update_for_transaction(r, fields)
                r.xack(STREAM_KEY, GROUP_NAME, entry_id)
                processed += 1
            except Exception as exc:  # noqa: BLE001
                print(
                    f"feature worker error on {entry_id}: {exc.__class__.__name__}: {exc}",
                    file=sys.stderr,
                )
    return processed


def run() -> None:  # pragma: no cover - process entrypoint
    url = os.environ.get("REDIS_URL")
    if not url:
        print("REDIS_URL not set", file=sys.stderr)
        sys.exit(1)
    r = redis.Redis.from_url(url, decode_responses=True)
    ensure_group(r)
    stop = {"flag": False}

    def _handle(*_a):
        stop["flag"] = True

    signal.signal(signal.SIGINT, _handle)
    signal.signal(signal.SIGTERM, _handle)

    total = 0
    while not stop["flag"]:
        try:
            n = process_once(r)
        except redis.ConnectionError:
            time.sleep(1)
            continue
        total += n
        if n and total % 100 == 0:
            print(f"feature worker: processed {total}")
    print(f"feature worker: stopping after {total} events")


if __name__ == "__main__":  # pragma: no cover
    run()
