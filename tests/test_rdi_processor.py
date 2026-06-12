"""Unit tests for the RDI processor's lag bookkeeping.

The processor lives in ``infra/rdi/processor.py``. These tests exercise the
small in-memory ``Stats`` object that tracks events and the last observed
replication lag — the value that ends up in the ``rdi:status`` heartbeat
doc and ultimately on the IRIS panel.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

RDI_DIR = Path(__file__).resolve().parent.parent / "infra" / "rdi"
if str(RDI_DIR) not in sys.path:
    sys.path.insert(0, str(RDI_DIR))

# Stub out psycopg2 / yaml only if missing — the processor module imports
# them at top level but we only exercise the dependency-free ``Stats``
# class. We deliberately do NOT stub ``redis`` because real ``redis`` is
# installed and other test modules rely on it being the genuine package.
for _modname in ("psycopg2", "psycopg2.extensions", "psycopg2.extras"):
    sys.modules.setdefault(_modname, type(sys)("stub"))
if not hasattr(sys.modules["psycopg2.extras"], "RealDictCursor"):
    sys.modules["psycopg2.extras"].RealDictCursor = object  # type: ignore[attr-defined]
if not hasattr(sys.modules["psycopg2.extensions"], "ISOLATION_LEVEL_AUTOCOMMIT"):
    sys.modules["psycopg2.extensions"].ISOLATION_LEVEL_AUTOCOMMIT = 0  # type: ignore[attr-defined]
if "yaml" not in sys.modules:
    sys.modules["yaml"] = type(sys)("stub")
    sys.modules["yaml"].safe_load = lambda *_a, **_k: {}  # type: ignore[attr-defined]

import processor  # noqa: E402


def test_bump_records_last_lag_ms() -> None:
    s = processor.Stats()
    assert s.last_lag_ms is None
    s.bump(42)
    assert s.last_lag_ms == 42
    assert s.events == 1


def test_bump_overwrites_with_most_recent_value() -> None:
    s = processor.Stats()
    s.bump(10)
    s.bump(250)
    s.bump(7)
    assert s.last_lag_ms == 7
    assert s.events == 3


def test_snapshot_includes_last_lag_ms_when_set() -> None:
    s = processor.Stats()
    s.bump(123)
    snap = s.snapshot()
    assert snap["last_lag_ms"] == 123
    assert snap["events_total"] == 1
    assert "last_event_at" in snap
    assert "started_at" in snap


def test_snapshot_last_lag_ms_is_none_before_first_event() -> None:
    s = processor.Stats()
    snap = s.snapshot()
    assert snap["last_lag_ms"] is None
    assert snap["events_total"] == 0


def test_bump_requires_lag_argument() -> None:
    s = processor.Stats()
    with pytest.raises(TypeError):
        s.bump()  # type: ignore[call-arg]
