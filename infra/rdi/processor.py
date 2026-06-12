"""Demo-grade Redis Data Integration processor.

Reads RDI-shaped YAML (`config.yaml` + `jobs/*.yaml`) and streams Postgres
row changes into the canonical Redis keys defined in the demo spec
(`customer:{id}`, `account:{id}`, `card:{id}`, `device:{id}`,
`merchant:{id}`, `mcc:{code}`, `tx:{id}`, `stream:transactions`,
`card:{card_id}:tx:recent`).

CDC uses Postgres LISTEN/NOTIFY (see `triggers.sql`); event-to-Redis
latency is typically <50ms on a local stack. Production deployments use
the managed RDI Helm chart with the same config shape.
"""
from __future__ import annotations

import json
import logging
import os
import re
import select
import signal
import sys
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

import psycopg2
import psycopg2.extensions
import redis
import yaml
from psycopg2.extras import RealDictCursor

CONFIG_DIR = Path(os.environ.get("RDI_CONFIG_DIR", "/etc/rdi/config"))
TRIGGERS_PATH = Path(__file__).resolve().parent / "triggers.sql"
HEARTBEAT_KEY = "rdi:status"
HEARTBEAT_INTERVAL_S = 1.0
ENV_VAR_RE = re.compile(r"\$\{([A-Z_][A-Z0-9_]*)\}")

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s rdi %(message)s",
)
log = logging.getLogger("rdi")


def _coerce(value: Any) -> Any:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, dict):
        return {k: _coerce(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_coerce(v) for v in value]
    return value


def _expand_env(text: str) -> str:
    return ENV_VAR_RE.sub(lambda m: os.environ.get(m.group(1), ""), text)


def _load_yaml(path: Path) -> dict:
    return yaml.safe_load(_expand_env(path.read_text())) or {}


def _ts(t: float | None) -> str | None:
    if t is None:
        return None
    return datetime.fromtimestamp(t, tz=timezone.utc).isoformat()


@dataclass
class Job:
    name: str
    table: str
    schema: str
    outputs: list[dict]


def load_jobs() -> list[Job]:
    jobs: list[Job] = []
    for p in sorted((CONFIG_DIR / "jobs").glob("*.yaml")):
        cfg = _load_yaml(p)
        src = cfg.get("source") or {}
        jobs.append(
            Job(
                name=cfg.get("name", p.stem),
                table=src["table"],
                schema=src.get("schema", "public"),
                outputs=cfg.get("output", []) or [],
            )
        )
    return jobs


@dataclass
class Stats:
    events: int = 0
    last_event_at: float | None = None
    last_lag_ms: int | None = None
    started_at: float = field(default_factory=time.time)
    lock: threading.Lock = field(default_factory=threading.Lock)

    def bump(self, lag_ms: int) -> None:
        with self.lock:
            self.events += 1
            self.last_event_at = time.time()
            self.last_lag_ms = lag_ms

    def snapshot(self) -> dict:
        with self.lock:
            return {
                "events_total": self.events,
                "last_event_at": _ts(self.last_event_at),
                "last_lag_ms": self.last_lag_ms,
                "started_at": _ts(self.started_at),
            }


def _render_key(template: str, row: dict) -> str:
    return template.format(**row)


def _stream_fields(row: dict) -> dict:
    out: dict = {}
    for k, v in row.items():
        if isinstance(v, bool) or not isinstance(v, (str, int, float)):
            out[k] = json.dumps(v)
        else:
            out[k] = v
    return out


def apply_outputs(r: redis.Redis, outputs: list[dict], row: dict | None, op: str) -> None:
    for block in outputs:
        if block.get("uses") != "redis.write":
            continue
        spec = block.get("with") or {}
        data_type = spec.get("data_type", "json")
        key_tpl = spec.get("key", "")
        if row is None:
            continue
        try:
            key = _render_key(key_tpl, row)
        except KeyError as e:
            log.warning("key template %r missing field %s; skipping", key_tpl, e)
            continue
        if op == "d":
            if data_type == "json":
                r.delete(key)
            continue
        coerced = _coerce(row)
        if data_type == "json":
            r.json().set(key, "$", coerced)
        elif data_type == "stream":
            r.xadd(key, _stream_fields(coerced))
        elif data_type == "list":
            cap = int(spec.get("cap", 0) or 0)
            payload = json.dumps(coerced)
            pipe = r.pipeline()
            if spec.get("direction", "lpush") == "rpush":
                pipe.rpush(key, payload)
            else:
                pipe.lpush(key, payload)
            if cap > 0:
                pipe.ltrim(key, 0, cap - 1)
            pipe.execute()
        else:
            log.warning("unsupported data_type=%s", data_type)


def pg_dsn() -> str:
    return (
        f"host={os.environ['POSTGRES_HOST']} "
        f"port={os.environ['POSTGRES_PORT']} "
        f"dbname={os.environ['POSTGRES_DB']} "
        f"user={os.environ['POSTGRES_USER']} "
        f"password={os.environ['POSTGRES_PASSWORD']} "
        f"connect_timeout=5"
    )


def wait_for_tables(tables: list[str], timeout_s: float = 180.0) -> None:
    deadline = time.time() + timeout_s
    last_err: Exception | None = None
    while time.time() < deadline:
        try:
            with psycopg2.connect(pg_dsn()) as conn, conn.cursor() as cur:
                cur.execute(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema='public'"
                )
                found = {row[0] for row in cur.fetchall()}
            missing = [t for t in tables if t not in found]
            if not missing:
                return
            log.info("waiting for source tables: %s", ",".join(sorted(missing)))
        except Exception as e:  # noqa: BLE001
            last_err = e
        time.sleep(2.0)
    raise RuntimeError(f"timed out waiting for tables; last_err={last_err}")


def install_triggers() -> None:
    sql = TRIGGERS_PATH.read_text()
    conn = psycopg2.connect(pg_dsn())
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
    finally:
        conn.close()


SEED_BATCH = 250


def _seed_one_row(pipe: redis.client.Pipeline, outputs: list[dict], row: dict,
                  caps: dict[str, int]) -> None:
    for block in outputs:
        if block.get("uses") != "redis.write":
            continue
        spec = block.get("with") or {}
        data_type = spec.get("data_type", "json")
        try:
            key = _render_key(spec.get("key", ""), row)
        except KeyError:
            continue
        coerced = _coerce(row)
        if data_type == "json":
            pipe.json().set(key, "$", coerced)
        elif data_type == "stream":
            pipe.xadd(key, _stream_fields(coerced))
        elif data_type == "list":
            payload = json.dumps(coerced)
            if spec.get("direction", "lpush") == "rpush":
                pipe.rpush(key, payload)
            else:
                pipe.lpush(key, payload)
            cap = int(spec.get("cap", 0) or 0)
            if cap > 0:
                caps[key] = cap


def seed_initial(jobs: list[Job], r: redis.Redis, stats: Stats) -> None:
    """Initial population via batched pipelines. Cap (LTRIM) is applied once
    per key at the end to keep round-trip count low against Redis Cloud."""
    with psycopg2.connect(pg_dsn()) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            for job in jobs:
                cur.execute(f'SELECT * FROM "{job.schema}"."{job.table}"')
                rows = cur.fetchall()
                caps: dict[str, int] = {}
                pipe = r.pipeline(transaction=False)
                n = 0
                for row in rows:
                    _seed_one_row(pipe, job.outputs, dict(row), caps)
                    n += 1
                    stats.bump(0)
                    if n % SEED_BATCH == 0:
                        pipe.execute()
                        pipe = r.pipeline(transaction=False)
                if n % SEED_BATCH != 0:
                    pipe.execute()
                if caps:
                    trim_pipe = r.pipeline(transaction=False)
                    for key, cap in caps.items():
                        trim_pipe.ltrim(key, 0, cap - 1)
                    trim_pipe.execute()
                log.info("seeded %d row(s) from %s", len(rows), job.table)


def listen_loop(
    jobs_by_table: dict[str, list[Job]],
    r: redis.Redis,
    stats: Stats,
    stop: threading.Event,
) -> None:
    conn = psycopg2.connect(pg_dsn())
    conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)
    with conn.cursor() as cur:
        cur.execute("LISTEN rdi_changes;")
    log.info("LISTEN rdi_changes")
    fetch_cur = conn.cursor(cursor_factory=RealDictCursor)
    while not stop.is_set():
        if select.select([conn], [], [], 1.0) == ([], [], []):
            continue
        conn.poll()
        events = []
        while conn.notifies:
            events.append(conn.notifies.pop(0))
        for n in events:
            try:
                payload = json.loads(n.payload)
            except Exception:  # noqa: BLE001
                log.warning("invalid payload received")
                continue
            table = payload.get("table")
            op = payload.get("op")
            pk_col = payload.get("pk_col")
            pk_val = payload.get("pk_val")
            pg_emit_ms = payload.get("pg_emit_ms")
            jobs = jobs_by_table.get(table, [])
            if not jobs:
                continue
            row: dict | None
            if op == "d":
                row = {pk_col: pk_val}
            else:
                fetch_cur.execute(
                    f'SELECT * FROM "public"."{table}" WHERE "{pk_col}"::text = %s',
                    (pk_val,),
                )
                fetched = fetch_cur.fetchone()
                row = dict(fetched) if fetched else None
            if row is None:
                continue
            for job in jobs:
                apply_outputs(r, job.outputs, row, op=op)
            if isinstance(pg_emit_ms, int):
                lag_ms = max(0, int(time.time() * 1000) - pg_emit_ms)
            else:
                lag_ms = 0
            stats.bump(lag_ms)


def heartbeat_loop(r: redis.Redis, stats: Stats, stop: threading.Event) -> None:
    while not stop.wait(HEARTBEAT_INTERVAL_S):
        snap = stats.snapshot()
        snap["last_heartbeat_at"] = _ts(time.time())
        try:
            r.json().set(HEARTBEAT_KEY, "$", snap)
        except Exception as e:  # noqa: BLE001
            log.warning("heartbeat write failed: %s", e.__class__.__name__)


def _redis_client() -> redis.Redis:
    url = os.environ.get("REDIS_URL", "")
    if not url:
        raise RuntimeError("REDIS_URL is required")
    return redis.Redis.from_url(url, decode_responses=False)


def main() -> None:
    cfg = _load_yaml(CONFIG_DIR / "config.yaml")
    tracked = list(((cfg.get("sources") or {}).get("source") or {}).get("tables", {}).keys())
    log.info("RDI processor starting; %d tracked tables", len(tracked))

    jobs = load_jobs()
    jobs_by_table: dict[str, list[Job]] = {}
    for j in jobs:
        jobs_by_table.setdefault(j.table, []).append(j)
    log.info("loaded %d job(s)", len(jobs))

    wait_for_tables(tracked)
    install_triggers()
    log.info("CDC triggers installed")

    r = _redis_client()
    r.ping()
    log.info("Redis connection OK")

    stats = Stats()
    seed_initial(jobs, r, stats)
    # Write an initial heartbeat so the lag endpoint is non-null immediately.
    r.json().set(
        HEARTBEAT_KEY,
        "$",
        {**stats.snapshot(), "last_heartbeat_at": _ts(time.time())},
    )

    stop = threading.Event()

    def _shutdown(*_: Any) -> None:
        log.info("shutdown requested")
        stop.set()

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    hb = threading.Thread(target=heartbeat_loop, args=(r, stats, stop), daemon=True)
    hb.start()
    listen_loop(jobs_by_table, r, stats, stop)


if __name__ == "__main__":
    try:
        main()
    except Exception:  # noqa: BLE001
        log.exception("RDI processor crashed")
        sys.exit(1)
