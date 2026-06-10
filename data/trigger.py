"""On-demand hero-transaction inserter.

Usage:
    python -m data.trigger mike
    python -m data.trigger jane
    python -m data.trigger alex

The same ``insert_trigger`` function is reused by the trigger API so the
dashboard and CLI produce byte-identical rows.
"""

from __future__ import annotations

import argparse
import json
import uuid
from datetime import datetime, timezone

from data import heroes
from data.db import cursor


def _ensure_alex_unknown_device(cur, spec: heroes.TriggerSpec) -> None:
    """Alex's fraud trigger uses a *new* device — make sure it exists in devices
    so the transaction's FK resolves. First-seen is set to "now" so feature
    extraction can see it as a brand-new device."""
    cur.execute("SELECT 1 FROM devices WHERE device_id = %s", (spec.device_id,))
    if cur.fetchone():
        return
    now = datetime.now(timezone.utc)
    cur.execute(
        """INSERT INTO devices (device_id, customer_id, device_type, os, fingerprint,
                                country, first_seen, last_seen)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
        (
            spec.device_id, heroes.ALEX.customer_id,
            spec.device_type or "mobile",
            spec.device_os or "Android 14",
            spec.device_fingerprint or "fp_unknown",
            spec.device_country or "BR",
            now, now,
        ),
    )


def insert_trigger(hero: heroes.HeroKey) -> dict:
    """Insert the scripted "next transaction" for one hero. Returns the row dict."""
    if hero not in heroes.HEROES:
        raise KeyError(f"unknown hero: {hero}")
    profile = heroes.HEROES[hero]
    spec = heroes.TRIGGERS[hero]
    tx_id = f"tx_trigger_{hero}_{uuid.uuid4().hex[:8]}"
    ts = datetime.now(timezone.utc)
    device_id = spec.device_id or profile.primary_device_id
    row = {
        "transaction_id": tx_id,
        "customer_id": profile.customer_id,
        "account_id": profile.account_id,
        "card_id": profile.card_id,
        "merchant_id": spec.merchant_id,
        "device_id": device_id,
        "amount": spec.amount,
        "currency": spec.currency,
        "country": spec.country,
        "city": spec.city,
        "is_foreign": spec.is_foreign,
        "is_card_present": spec.is_card_present,
        "status": "pending",
        "ts": ts,
    }
    with cursor() as (conn, cur):
        if hero == "alex":
            _ensure_alex_unknown_device(cur, spec)
        cur.execute(
            """INSERT INTO transactions
               (transaction_id, customer_id, account_id, card_id, merchant_id, device_id,
                amount, currency, country, city, is_foreign, is_card_present, status, ts)
               VALUES (%(transaction_id)s, %(customer_id)s, %(account_id)s, %(card_id)s,
                       %(merchant_id)s, %(device_id)s, %(amount)s, %(currency)s,
                       %(country)s, %(city)s, %(is_foreign)s, %(is_card_present)s,
                       %(status)s, %(ts)s)""",
            row,
        )
    row["ts"] = row["ts"].isoformat()
    return row


def main() -> None:
    parser = argparse.ArgumentParser(description="Insert a hero customer's next transaction.")
    parser.add_argument("hero", choices=sorted(heroes.HEROES.keys()))
    args = parser.parse_args()
    row = insert_trigger(args.hero)
    print(json.dumps(row, indent=2, default=str))


if __name__ == "__main__":
    main()
