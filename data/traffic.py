"""Background traffic generator — ~1 tx/sec of realistic noise.

Picks random background customers (never heroes) and inserts plausible
transactions so the RDI feed in the dashboard is never empty during the demo.

Run: ``python -m data.traffic`` (Ctrl+C to stop).
Tune rate via ``--rate`` (tx per second, default 1.0).
"""

from __future__ import annotations

import argparse
import random
import signal
import sys
import time
import uuid
from datetime import datetime, timezone

from data import heroes
from data.db import cursor

HERO_IDS = {h.customer_id for h in heroes.HEROES.values()}


def _load_pool(cur) -> dict:
    """Pull the small lookup tables once; they're <1k rows total."""
    cur.execute("""
        SELECT c.customer_id, c.home_country, c.home_city,
               a.account_id, ca.card_id,
               (SELECT device_id FROM devices d
                WHERE d.customer_id = c.customer_id LIMIT 1) AS device_id
          FROM customers c
          JOIN accounts a ON a.customer_id = c.customer_id
          JOIN cards ca ON ca.account_id = a.account_id
         WHERE c.customer_id <> ALL(%s)
    """, (list(HERO_IDS),))
    customers = [
        {"customer_id": r[0], "home_country": r[1], "home_city": r[2],
         "account_id": r[3], "card_id": r[4], "device_id": r[5]}
        for r in cur.fetchall() if r[5] is not None
    ]
    cur.execute("SELECT merchant_id, country, city FROM merchants")
    merchants = [{"merchant_id": r[0], "country": r[1], "city": r[2]} for r in cur.fetchall()]
    return {"customers": customers, "merchants": merchants}


def _build_row(pool: dict, rng: random.Random) -> dict:
    c = rng.choice(pool["customers"])
    m = rng.choice(pool["merchants"])
    is_foreign = m["country"] != c["home_country"]
    return {
        "transaction_id": f"tx_live_{uuid.uuid4().hex[:12]}",
        "customer_id": c["customer_id"],
        "account_id": c["account_id"],
        "card_id": c["card_id"],
        "merchant_id": m["merchant_id"],
        "device_id": c["device_id"],
        "amount": round(rng.uniform(2.0, 220.0), 2),
        "currency": "USD" if not is_foreign else m["country"],
        "country": m["country"], "city": m["city"],
        "is_foreign": is_foreign, "is_card_present": rng.random() > 0.25,
        "status": "approved",
        "ts": datetime.now(timezone.utc),
    }


_INSERT_SQL = """
    INSERT INTO transactions
    (transaction_id, customer_id, account_id, card_id, merchant_id, device_id,
     amount, currency, country, city, is_foreign, is_card_present, status, ts)
    VALUES (%(transaction_id)s, %(customer_id)s, %(account_id)s, %(card_id)s,
            %(merchant_id)s, %(device_id)s, %(amount)s, %(currency)s,
            %(country)s, %(city)s, %(is_foreign)s, %(is_card_present)s,
            %(status)s, %(ts)s)
"""


def run(rate: float) -> None:
    if rate <= 0:
        raise ValueError("rate must be > 0")
    interval = 1.0 / rate
    rng = random.Random()  # live noise — not seeded; the deterministic seed is in seed.py.
    stop = {"flag": False}

    def _handle(_signum, _frame):  # noqa: ANN001
        stop["flag"] = True
    signal.signal(signal.SIGINT, _handle)
    signal.signal(signal.SIGTERM, _handle)

    with cursor() as (conn, cur):
        pool = _load_pool(cur)
        if not pool["customers"]:
            print("no background customers found — run `make seed` first", file=sys.stderr)
            return
        emitted = 0
        next_tick = time.monotonic()
        while not stop["flag"]:
            row = _build_row(pool, rng)
            cur.execute(_INSERT_SQL, row)
            conn.commit()
            emitted += 1
            if emitted % 30 == 0:
                print(f"traffic: emitted {emitted} tx")
            next_tick += interval
            sleep_for = next_tick - time.monotonic()
            if sleep_for > 0:
                time.sleep(sleep_for)
            else:
                next_tick = time.monotonic()
        print(f"traffic stopped after {emitted} tx")


def main() -> None:
    parser = argparse.ArgumentParser(description="Background transaction generator.")
    parser.add_argument("--rate", type=float, default=1.0, help="transactions per second (default 1)")
    args = parser.parse_args()
    run(args.rate)


if __name__ == "__main__":
    main()
