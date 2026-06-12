"""Trigger-layer test for the RDI NOTIFY payload.

Asserts that ``infra/rdi/triggers.sql`` builds a payload that includes the
Postgres-side emit timestamp (``pg_emit_ms``) sourced from
``clock_timestamp()``. The processor uses this field to compute the true
replication lag (Postgres → Redis write delay), so its presence in the
trigger function is a hard contract.
"""

from __future__ import annotations

import re
from pathlib import Path

TRIGGERS_SQL = Path(__file__).resolve().parent.parent / "infra" / "rdi" / "triggers.sql"


def _sql() -> str:
    return TRIGGERS_SQL.read_text()


def test_payload_includes_pg_emit_ms_field() -> None:
    sql = _sql()
    assert "'pg_emit_ms'" in sql, "NOTIFY payload must include a pg_emit_ms field"


def test_pg_emit_ms_sourced_from_clock_timestamp() -> None:
    sql = _sql()
    # The pg_emit_ms entry must be computed from clock_timestamp() in ms.
    # Match the json_build_object key/value pair and confirm both pieces are
    # present (whitespace-insensitive).
    flattened = re.sub(r"\s+", " ", sql)
    assert (
        "'pg_emit_ms', (EXTRACT(EPOCH FROM clock_timestamp()) * 1000)::bigint"
        in flattened
    ), "pg_emit_ms must come from clock_timestamp() converted to bigint ms"


def test_payload_still_carries_table_op_pk() -> None:
    # Backwards-compat: existing payload fields must remain so the processor
    # can still route the event.
    sql = _sql()
    for field in ("'table'", "'op'", "'pk_col'", "'pk_val'"):
        assert field in sql, f"trigger payload regressed: missing {field}"
