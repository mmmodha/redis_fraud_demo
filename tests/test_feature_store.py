"""Unit tests for the feature store.

Runs against fakeredis so the suite is hermetic; the same code path executes
against Redis Cloud in the live stack. The "hero customer" tests mirror the
seed shapes from ``data/seed.py`` to assert features are sensible after a
seeded run.

Run: ``pip install -r tests/requirements.txt && pytest tests/test_feature_store.py``
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timedelta, timezone

import pytest

fakeredis = pytest.importorskip("fakeredis")

from backend.app import feature_worker  # noqa: E402
from backend.app.features import FeatureStore  # noqa: E402


# ---------- helpers ----------------------------------------------------------


def _fake_redis():
    return fakeredis.FakeStrictRedis(decode_responses=True)


def _tx(
    card_id: str,
    *,
    tx_id: str,
    amount: float,
    country: str,
    mcc: str,
    device_id: str,
    ts: float,
    merchant_id: str = "merch_x",
) -> dict:
    return {
        "transaction_id": tx_id,
        "card_id": card_id,
        "merchant_id": merchant_id,
        "device_id": device_id,
        "amount": str(amount),
        "country": country,
        "merchant_category": mcc,
        "ts": str(ts),
    }


def _now() -> float:
    return datetime.now(timezone.utc).timestamp()


# ---------- direct update_for_transaction tests ------------------------------


def test_mike_steady_state_features_look_sensible():
    """Mike: low-risk US-only txs over the past 30 days, single device."""
    r = _fake_redis()
    now = _now()
    # Feed oldest -> newest (the order RDI delivers from the stream).
    for i in range(30):
        ts = now - ((30 - i) * 3600)  # one per hour, oldest first
        feature_worker.update_for_transaction(
            r,
            _tx(
                "card_mike_visa", tx_id=f"tx_mike_{i:03d}",
                amount=20.0 + i * 0.5, country="US",
                mcc="5814" if i % 2 == 0 else "5411",
                device_id="dev_mike_iphone", ts=ts,
            ),
        )
    feats = FeatureStore(r).get_features("card_mike_visa")
    assert feats["velocity_1h"] >= 1
    assert feats["velocity_24h"] >= 20
    assert feats["velocity_7d"] >= 30
    assert feats["geo_entropy"] == 0.0  # only US
    top = feats["mcc_top_3"].split(",")
    assert {"5814", "5411"}.issubset(set(top))
    assert feats["new_device_24h"] == 0  # device first seen 30h ago
    assert feats["amount_avg_30d"] > 0


def test_jane_mixed_geo_yields_nonzero_entropy():
    """Jane: US baseline plus a chunk of SG history → entropy > 0."""
    r = _fake_redis()
    now = _now()
    events = []
    for i in range(20):
        events.append((now - (20 - i) * 3600 * 24, "US"))
    for i in range(6):
        events.append((now - (i * 3600 * 24 + 3600), "SG"))
    events.sort(key=lambda e: e[0])  # chronological
    for idx, (ts, country) in enumerate(events):
        feature_worker.update_for_transaction(
            r,
            _tx("card_jane_visa", tx_id=f"tx_jane_{idx:02d}",
                amount=30.0, country=country, mcc="5814",
                device_id="dev_jane_iphone", ts=ts),
        )
    feats = FeatureStore(r).get_features("card_jane_visa")
    assert feats["geo_entropy"] > 0.0
    assert feats["velocity_7d"] >= 7
    assert feats["new_device_24h"] == 0


def test_alex_new_device_in_24h_flags_one():
    """Alex: clean US history, then a brand-new device + BR + 5732 trigger."""
    r = _fake_redis()
    now = _now()
    # 25 clean US tx on Alex's primary device, oldest-first.
    for i in range(25):
        feature_worker.update_for_transaction(
            r,
            _tx("card_alex_visa", tx_id=f"tx_alex_{i:03d}",
                amount=50.0, country="US", mcc="5411",
                device_id="dev_alex_macbook",
                ts=now - (25 - i) * 3600 * 24),
        )
    # The fraud trigger: brand-new device + new country, high-risk mcc.
    feature_worker.update_for_transaction(
        r,
        _tx("card_alex_visa", tx_id="tx_alex_trigger",
            amount=2400.0, country="BR", mcc="5732",
            device_id="dev_alex_unknown_android", ts=now),
    )
    feats = FeatureStore(r).get_features("card_alex_visa")
    assert feats["new_device_24h"] == 1
    assert feats["amount_max_24h"] >= 2400.0
    assert feats["geo_entropy"] > 0.0
    assert feats["mcc_top_3"].split(",")[0] == "5411"  # legit pattern still dominates


# ---------- out-of-order ingest (event-time vs ingest-time) -----------------


def test_velocity_uses_event_time_not_ingest_order():
    """Wave 3c regression: if RDI delivers history in burst order, the velocity
    window of an OLDER event must not absorb "future" events that happen to be
    further along the timeline. ``feat:{card}.velocity_1h`` is bounded by the
    event's own ``ts``, not by the open-ended ``s >= ts - 1h`` lower edge alone.
    """
    r = _fake_redis()
    now = _now()
    # 30 transactions, one per day, but ingested oldest-first then *future-most*
    # last so the trailing event is the "May 7"-equivalent in the middle of the
    # series — mirroring what the live demo observed (velocity_1h=19 on Mike).
    days = list(range(30))
    rng_order = days[:15] + list(reversed(days[15:]))
    for processing_idx, day_offset in enumerate(rng_order):
        ts = now - day_offset * 86400
        feature_worker.update_for_transaction(
            r,
            _tx(
                "card_event_time", tx_id=f"tx_evt_{processing_idx:03d}",
                amount=10.0, country="US", mcc="5814",
                device_id="dev_evt", ts=ts,
            ),
        )
    feats = FeatureStore(r).get_features("card_event_time")
    # The last-processed event's ts is day 15 (somewhere in the middle of the
    # timeline). With the bug, velocity_1h would equal the number of events with
    # a *later* ts already in the zset (≥ ~14). With the fix it is exactly 1
    # because no other event shares its 1h window.
    assert feats["velocity_1h"] == 1
    # 24h window: only the current event is within (events are 1 day apart and
    # the upper bound is the event's own ts, so the day-16 neighbour at exactly
    # ``ts - 86400`` is the boundary — both 1 and 2 are acceptable.
    assert feats["velocity_24h"] in (1, 2)
    # 7d window at day 15 covers days 15..22 (inclusive boundaries).
    assert feats["velocity_7d"] == 8


# ---------- read latency / API ----------------------------------------------


def test_get_features_returns_typed_dict():
    r = _fake_redis()
    feature_worker.update_for_transaction(
        r,
        _tx("card_test", tx_id="t1", amount=10.0, country="US", mcc="5814",
            device_id="d1", ts=_now()),
    )
    store = FeatureStore(r)
    feats = store.get_features("card_test")
    assert isinstance(feats["velocity_1h"], int)
    assert isinstance(feats["amount_avg_30d"], float)
    assert isinstance(feats["mcc_top_3"], str)
    summary = store.latency_summary()
    assert summary["count"] == 1
    assert summary["p99_ms"] is not None


def test_latency_summary_empty_when_no_reads():
    store = FeatureStore(_fake_redis())
    summary = store.latency_summary()
    assert summary == {"count": 0, "p50_ms": None, "p99_ms": None, "max_ms": None}


# ---------- stream-consumer end-to-end --------------------------------------


def test_stream_consumer_processes_and_acks():
    r = _fake_redis()
    feature_worker.ensure_group(r)
    now = _now()
    r.xadd(feature_worker.STREAM_KEY, _tx(
        "card_stream", tx_id="s1", amount=12.5, country="US",
        mcc="5411", device_id="dev_s", ts=now,
    ))
    r.xadd(feature_worker.STREAM_KEY, _tx(
        "card_stream", tx_id="s2", amount=88.0, country="CA",
        mcc="5732", device_id="dev_s", ts=now,
    ))

    processed = feature_worker.process_once(r, count=10, block_ms=None, consumer="test-c")
    assert processed == 2

    feats = FeatureStore(r).get_features("card_stream")
    assert feats["velocity_24h"] == 2
    assert feats["geo_entropy"] > 0.0

    # Pending should be empty after ack.
    pending = r.xpending(feature_worker.STREAM_KEY, feature_worker.GROUP_NAME)
    assert pending["pending"] == 0


def test_consumer_resumes_after_restart():
    r = _fake_redis()
    feature_worker.ensure_group(r)
    r.xadd(feature_worker.STREAM_KEY, _tx(
        "card_resume", tx_id="r1", amount=5.0, country="US",
        mcc="5814", device_id="dev_r", ts=_now(),
    ))
    # First worker reads + acks.
    assert feature_worker.process_once(r, count=10, block_ms=None, consumer="c1") == 1
    # A new worker on the same group must NOT redeliver acked entries.
    assert feature_worker.process_once(r, count=10, block_ms=None, consumer="c2") == 0


# ---------- entropy helper --------------------------------------------------


def test_shannon_entropy_normalized_bounds():
    assert feature_worker.shannon_entropy_normalized([]) == 0.0
    assert feature_worker.shannon_entropy_normalized(["US"]) == 0.0
    assert feature_worker.shannon_entropy_normalized(["US", "US", "US"]) == 0.0
    # Two equally likely countries -> 1.0
    assert feature_worker.shannon_entropy_normalized(["US", "CA"]) == pytest.approx(1.0)
    # Skewed distribution -> between 0 and 1
    val = feature_worker.shannon_entropy_normalized(["US"] * 9 + ["CA"])
    assert 0.0 < val < 1.0


def test_pending_review_overlay_elevates_alex_geo_entropy():
    from app import features as feat_mod

    r = _fake_redis()
    r.hset("feat:card_alex_visa", mapping={"geo_entropy": "0.0", "new_device_24h": "0"})
    r.json().set(
        "pending_review:cust_alex",
        "$",
        {
            "foreign_country": True,
            "impossible_travel": True,
            "device_first_seen_today": True,
        },
    )
    pending = feat_mod.read_pending_review(r, "cust_alex")
    overlaid = feat_mod.overlay_pending_fraud_signals(
        feat_mod._coerce(r.hgetall("feat:card_alex_visa")),
        pending,
    )
    assert overlaid["geo_entropy"] >= 0.91
    assert overlaid["new_device_24h"] == 1
    assert overlaid["impossible_travel"] is True
