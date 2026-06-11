"""Tests for the Wave 7f+ deterministic verdict-fast policy engine.

Hero parity: the three canonical demo customers must agree with the existing
``/agent/score`` LLM verdicts (approve/approve/block). Edge cases cover the
two interesting decision paths the rule engine adds on top of that.
"""

from __future__ import annotations

import pytest

from app.policy_engine import evaluate_verdict_fast


# ---------- helpers --------------------------------------------------------

def _pending(**overrides):
    base = {
        "transaction_id": "tx_test",
        "amount": 100.0,
        "currency": "USD",
        "merchant_name": "Test Merchant",
        "merchant_country": "US",
        "merchant_category": "5814",
        "device_id": "dev_known",
        "device_first_seen_today": False,
        "foreign_country": False,
        "impossible_travel": False,
        "occurred_at": "2026-06-11T00:00:00Z",
    }
    base.update(overrides)
    return base


def _memory_with_travel(country_name: str = "Singapore"):
    return {
        "customer_id": "cust_jane",
        "travel_windows": [
            {"start_date": "2099-11-10", "end_date": "2099-11-17",
             "destinations": [country_name], "source": "seed"},
        ],
        "conversation_notes": [],
    }


# ---------- hero parity ----------------------------------------------------

def test_mike_approves_no_pending_review():
    # Mike's pending_review key is absent in Redis → trivial approve path.
    result = evaluate_verdict_fast(
        customer_id="cust_mike", pending_review=None, memory=None,
    )
    assert result["verdict"] == "approve"
    assert result["confidence"] >= 0.9
    assert "no_pending_review" in result["signals"]


def test_jane_approves_no_pending_review():
    # Jane likewise has no pending_review staged in the demo seed.
    result = evaluate_verdict_fast(
        customer_id="cust_jane",
        pending_review=None,
        memory=_memory_with_travel("Singapore"),
    )
    assert result["verdict"] == "approve"
    assert "no_pending_review" in result["signals"]


def test_alex_blocks_first_seen_device_foreign():
    # Alex has a pending_review with first-seen device + foreign + impossible
    # travel; no declared travel window → block.
    pending = _pending(
        merchant_country="BR", foreign_country=True,
        device_first_seen_today=True, impossible_travel=True,
        device_id="dev_alex_unknown_android",
    )
    result = evaluate_verdict_fast(
        customer_id="cust_alex", pending_review=pending, memory=None,
    )
    assert result["verdict"] == "block"
    assert result["confidence"] >= 0.9
    assert any("first_seen_device" in s for s in result["signals"])
    assert any("foreign_country:BR" in s for s in result["signals"])


def test_sarah_step_up_review_with_travel_value_and_novel_mcc():
    # Sarah: travel + device confirmed, no velocity violation, legit merchant —
    # but value 5x typical + novel jewelry MCC + behavior anomaly → review.
    pending = _pending(
        merchant_country="US", foreign_country=False,
        device_first_seen_today=False, impossible_travel=False,
        device_id="dev_sarah_iphone",
        amount=1450.0,
        customer_p95_spend=280.0,
        mcc_name="Jewelry & Watches",
        mcc_novel_for_customer=True,
        behavior_memory_flags_anomaly=True,
        travel_context_confirmed=True,
        merchant_legitimate=True,
    )
    result = evaluate_verdict_fast(
        customer_id="cust_sarah", pending_review=pending, memory=None,
    )
    assert result["verdict"] == "review"
    assert any("step_up_required" in s for s in result["signals"])


# ---------- edge cases -----------------------------------------------------

def test_no_pending_review_path_approves_even_without_memory():
    # No in-flight tx + no memory document → still approve.
    result = evaluate_verdict_fast(
        customer_id="cust_other", pending_review=None, memory=None,
    )
    assert result["verdict"] == "approve"
    assert result["signals"] == ["no_pending_review"]


def test_first_seen_device_no_declared_travel_blocks():
    # Foreign tx on a first-seen device with no matching travel window
    # → block. The hero-Alex shape generalised.
    pending = _pending(
        merchant_country="JP", foreign_country=True,
        device_first_seen_today=True,
        device_id="dev_new_phone",
    )
    result = evaluate_verdict_fast(
        customer_id="cust_other", pending_review=pending,
        memory={"travel_windows": []},
    )
    assert result["verdict"] == "block"
    assert any("first_seen_device:dev_new_phone(JP)" in s for s in result["signals"])


# ---------- declared-travel override --------------------------------------

def test_foreign_tx_with_matching_travel_window_approves():
    # Same shape as Alex BUT with a declared travel window matching the
    # merchant country — the memory signal flips block → approve.
    pending = _pending(
        merchant_country="SG", foreign_country=True,
        device_first_seen_today=False,
        device_id="dev_jane_iphone",
    )
    result = evaluate_verdict_fast(
        customer_id="cust_jane", pending_review=pending,
        memory=_memory_with_travel("Singapore"),
    )
    assert result["verdict"] == "approve"
    assert any("declared_travel_window_matches_merchant_country:SG" in s
               for s in result["signals"])
