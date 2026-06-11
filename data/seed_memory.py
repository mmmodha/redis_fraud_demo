"""One-shot Agent Memory seeder: Postgres ``customer_memory_seed`` → Redis ``mem:*``.

Runs after ``data.seed`` (which writes the Postgres source) and is independent
of RDI (RDI does not touch ``mem:*`` keys — see ``docs/agent-memory.md``).

Idempotent: skips customers whose ``mem:{id}`` key already exists in Redis so
re-running after a partial demo run is safe.

Also seeds two additional Redis-only entity families used by the chatbot's
context-surface tools (Wave 7e):
  * ``disputes:{customer_id}``        — per-customer dispute log
  * ``pending_review:{customer_id}``  — in-flight transaction at the agent's
                                        review door

Both are NX-guarded so reseed is idempotent.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone

import redis

from data.db import cursor
from data import heroes


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _canonicalise(customer_id: str, source: dict) -> dict:
    """Map the data-generator's seed shape onto the canonical Agent Memory schema.

    The generator wrote ``{"notes": [{text, source, tags}], "travel_window":
    {start, end, destination}}``. The canonical schema uses ``travel_windows``
    (list) and ``conversation_notes`` (list). See ``docs/agent-memory.md``.
    """
    travel_windows = []
    tw = source.get("travel_window")
    if tw and tw.get("start") and tw.get("end"):
        dest = tw.get("destination")
        travel_windows.append({
            "start_date": tw["start"],
            "end_date": tw["end"],
            "destinations": [dest] if isinstance(dest, str) else list(dest or []),
            "source": "seed",
        })
    conversation_notes = []
    for note in source.get("notes", []) or []:
        text = note.get("text")
        if not text:
            continue
        conversation_notes.append({
            "timestamp": _now_iso(),
            "text": text,
            "source": note.get("source", "seed"),
        })
    return {
        "customer_id": customer_id,
        "travel_windows": travel_windows,
        "prior_disputes": [],
        "flagged_devices": [],
        "conversation_notes": conversation_notes,
        "last_updated_at": _now_iso(),
    }


def _redis_client() -> redis.Redis:
    url = os.environ.get("REDIS_URL")
    if not url:
        raise SystemExit("REDIS_URL is not set — cannot seed Agent Memory.")
    return redis.Redis.from_url(url)


def seed(client: redis.Redis | None = None) -> dict[str, int]:
    """Walk ``customer_memory_seed`` and JSON.SET each row into Redis with NX.

    Returns counts for logging: ``{"written": N, "skipped": N}``.
    """
    client = client or _redis_client()
    written = 0
    skipped = 0
    with cursor() as (_conn, cur):
        cur.execute("SELECT customer_id, memory_json FROM customer_memory_seed")
        rows = cur.fetchall()
    for customer_id, memory_json in rows:
        # psycopg2 returns JSONB as dict already; tolerate str just in case.
        source = memory_json if isinstance(memory_json, dict) else json.loads(memory_json)
        canonical = _canonicalise(customer_id, source)
        ok = client.json().set(f"mem:{customer_id}", "$", canonical, nx=True)
        if ok:
            written += 1
        else:
            skipped += 1
    return {"written": written, "skipped": skipped}


# ---------- Wave 7e: disputes / pending_review / hero memory enrichment ----

# Static dispute seed. Heroes get a zero-length list so the tool returns
# "0 disputes" deterministically. A handful of background customers get
# small dispute lists so the tool isn't trivially always-empty.
_DISPUTE_SEED: dict[str, list[dict]] = {
    heroes.MIKE.customer_id: [],
    heroes.JANE.customer_id: [],
    heroes.ALEX.customer_id: [],
    heroes.SARAH.customer_id: [],
    "cust_bg_0007": [
        {
            "dispute_id": "disp_bg_0007_001",
            "transaction_id": "tx_bg_00042",
            "merchant_name": "Quasi-Cash Exchange Co.",
            "amount": 320.00, "currency": "USD",
            "opened_at": "2026-04-12T10:14:00Z",
            "status": "closed", "outcome": "refunded",
            "reason": "unauthorised",
        },
    ],
    "cust_bg_0013": [
        {
            "dispute_id": "disp_bg_0013_001",
            "transaction_id": "tx_bg_00198",
            "merchant_name": "BetNow Gaming",
            "amount": 89.99, "currency": "USD",
            "opened_at": "2026-05-02T22:30:00Z",
            "status": "closed", "outcome": "denied",
            "reason": "friendly_fraud",
        },
        {
            "dispute_id": "disp_bg_0013_002",
            "transaction_id": "tx_bg_00211",
            "merchant_name": "Crypto Buy Inc.",
            "amount": 410.00, "currency": "USD",
            "opened_at": "2026-05-22T18:05:00Z",
            "status": "open", "outcome": "pending",
            "reason": "unauthorised",
        },
    ],
    "cust_bg_0029": [
        {
            "dispute_id": "disp_bg_0029_001",
            "transaction_id": "tx_bg_00307",
            "merchant_name": "Lux Watch Atelier",
            "amount": 1450.00, "currency": "EUR",
            "opened_at": "2026-03-30T09:12:00Z",
            "status": "closed", "outcome": "refunded",
            "reason": "merchant_error",
        },
    ],
}


def seed_disputes(client: redis.Redis | None = None) -> dict[str, int]:
    """JSON.SET each ``disputes:{customer_id}`` doc with NX. Idempotent."""
    client = client or _redis_client()
    written = 0
    skipped = 0
    for customer_id, items in _DISPUTE_SEED.items():
        doc = {"customer_id": customer_id, "items": items}
        ok = client.json().set(f"disputes:{customer_id}", "$", doc, nx=True)
        if ok:
            written += 1
        else:
            skipped += 1
    return {"written": written, "skipped": skipped}


def seed_pending_review(client: redis.Redis | None = None) -> dict[str, int]:
    """Stage the Alex + Sarah trigger transactions as pending review records.

    Mirrors the trigger specs in ``data.heroes`` but is written Redis-only
    (no Postgres row, no commit to settled history).
    """
    client = client or _redis_client()
    occurred_at = (datetime.now(timezone.utc) - timedelta(minutes=2)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    alex_trigger = heroes.TRIGGERS["alex"]
    alex_pending = {
        "transaction_id": "tx_alex_pending_br_electronics",
        "customer_id": heroes.ALEX.customer_id,
        "amount": 1240.00,
        "currency": alex_trigger.currency,
        "merchant_name": alex_trigger.merchant_name,
        "merchant_country": alex_trigger.merchant_country,
        "merchant_city": alex_trigger.merchant_city,
        "merchant_category": alex_trigger.merchant_category,
        "device_id": alex_trigger.device_id or "dev_alex_unknown_android",
        "device_first_seen_today": True,
        "foreign_country": True,
        "impossible_travel": True,
        "occurred_at": occurred_at,
    }
    sarah_trigger = heroes.TRIGGERS["sarah"]
    sarah_pending = {
        "transaction_id": "tx_sarah_pending_tiffany_ny",
        "customer_id": heroes.SARAH.customer_id,
        "amount": sarah_trigger.amount,
        "currency": sarah_trigger.currency,
        "merchant_name": sarah_trigger.merchant_name,
        "merchant_country": sarah_trigger.merchant_country,
        "merchant_city": sarah_trigger.merchant_city,
        "merchant_category": sarah_trigger.merchant_category,
        "device_id": heroes.SARAH.primary_device_id,
        "device_first_seen_today": False,
        "foreign_country": False,
        "impossible_travel": False,
        # Step-up signals the policy engine reads.
        "customer_p95_spend": 280.00,
        "mcc_name": "Jewelry & Watches",
        "mcc_novel_for_customer": True,
        "behavior_memory_flags_anomaly": True,
        "travel_context_confirmed": True,
        "merchant_legitimate": True,
        "occurred_at": occurred_at,
    }
    written = 0
    skipped = 0
    for cust_id, pending in (
        (heroes.ALEX.customer_id, alex_pending),
        (heroes.SARAH.customer_id, sarah_pending),
    ):
        ok = client.json().set(f"pending_review:{cust_id}", "$", pending, nx=True)
        if ok:
            written += 1
        else:
            skipped += 1
    return {"written": written, "skipped": skipped}


def _ensure_mem_skeleton(client: redis.Redis, customer_id: str) -> None:
    skeleton = {
        "customer_id": customer_id,
        "travel_windows": [],
        "prior_disputes": [],
        "flagged_devices": [],
        "conversation_notes": [],
        "last_updated_at": _now_iso(),
    }
    client.json().set(f"mem:{customer_id}", "$", skeleton, nx=True)


def _has_note_with_text(client: redis.Redis, customer_id: str, text: str) -> bool:
    raw = client.json().get(f"mem:{customer_id}", "$.conversation_notes")
    if not raw:
        return False
    notes = raw[0] if isinstance(raw, list) and raw and isinstance(raw[0], list) else raw
    if not isinstance(notes, list):
        return False
    return any(isinstance(n, dict) and n.get("text") == text for n in notes)


def _has_travel_window(
    client: redis.Redis, customer_id: str, start_date: str, end_date: str
) -> bool:
    raw = client.json().get(f"mem:{customer_id}", "$.travel_windows")
    if not raw:
        return False
    windows = raw[0] if isinstance(raw, list) and raw and isinstance(raw[0], list) else raw
    if not isinstance(windows, list):
        return False
    return any(
        isinstance(w, dict)
        and w.get("start_date") == start_date
        and w.get("end_date") == end_date
        for w in windows
    )


_ALEX_NOTES = (
    "customer has never declared international travel; only uses "
    "dev_alex_macbook in SF",
    "customer baseline: SF-only, low velocity, no new devices in 8 months",
)

_MIKE_NOTES = (
    "customer baseline: Austin pattern-of-life — coffee, grocery, gas, "
    "Spotify; no foreign spend ever observed",
)

_SARAH_NOTES = (
    "customer baseline: Seattle pattern-of-life — coffee, grocery, gas, "
    "gym, dining; quarterly East Coast business trips (hotel + dining + "
    "airport) — no retail, no jewelry, no foreign spend",
    "step-up policy: high-value retail anomalies during travel should "
    "route to OTP step-up rather than block — false-blocking on Sarah's "
    "travel days has high CLV cost",
)

_JANE_PAST_TRAVEL_NOTE = (
    "Customer declared prior travel: Tokyo, 14–22 May 2026 "
    "(returned without incident) — pattern of declaring trips ahead of time."
)


def seed_hero_memory_enrichment(
    client: redis.Redis | None = None,
) -> dict[str, int]:
    """Add Wave 7e narrative hooks to hero Agent Memory docs.

    Idempotent: each note / travel-window is matched on content before
    re-appending. Counts the *appends*, not the customers touched.
    """
    client = client or _redis_client()
    appended = 0
    now = _now_iso()
    for customer_id, notes in (
        (heroes.ALEX.customer_id, _ALEX_NOTES),
        (heroes.MIKE.customer_id, _MIKE_NOTES),
        (heroes.SARAH.customer_id, _SARAH_NOTES),
    ):
        _ensure_mem_skeleton(client, customer_id)
        for text in notes:
            if _has_note_with_text(client, customer_id, text):
                continue
            entry = {"timestamp": now, "text": text, "source": "seed"}
            client.json().arrappend(
                f"mem:{customer_id}", "$.conversation_notes", entry
            )
            appended += 1
        client.json().set(f"mem:{customer_id}", "$.last_updated_at", now)

    # Jane: layer a prior travel-notify note (Tokyo, May 2026) onto her
    # existing mem doc to back the "pattern of declaring trips" chatbot hook.
    # Stored as a conversation_note rather than a travel_window because
    # ``agent_memory.get_memory`` strips travel_windows past their end_date.
    # This is memory, not a dispute — disputes go through seed_disputes().
    _ensure_mem_skeleton(client, heroes.JANE.customer_id)
    if not _has_note_with_text(client, heroes.JANE.customer_id, _JANE_PAST_TRAVEL_NOTE):
        entry = {"timestamp": now, "text": _JANE_PAST_TRAVEL_NOTE, "source": "seed"}
        client.json().arrappend(
            f"mem:{heroes.JANE.customer_id}", "$.conversation_notes", entry
        )
        appended += 1
    client.json().set(f"mem:{heroes.JANE.customer_id}", "$.last_updated_at", now)
    return {"appended": appended}


def main() -> None:
    client = _redis_client()
    mem_result = seed(client)
    enrich_result = seed_hero_memory_enrichment(client)
    disputes_result = seed_disputes(client)
    pending_result = seed_pending_review(client)
    print(
        f"agent-memory seeded: written={mem_result['written']} "
        f"skipped={mem_result['skipped']} "
        f"enriched_appends={enrich_result['appended']} "
        f"disputes_written={disputes_result['written']} "
        f"disputes_skipped={disputes_result['skipped']} "
        f"pending_written={pending_result['written']} "
        f"pending_skipped={pending_result['skipped']}"
    )


if __name__ == "__main__":
    main()
