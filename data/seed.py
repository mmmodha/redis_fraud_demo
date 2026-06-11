"""Deterministic synthetic seed for the fraud-detection demo.

Run: ``python -m data.seed`` (inside a container with $DATABASE_URL).
Rerunning is safe — schema.sql drops + recreates every table.

All randomness comes from Faker(seed=SEED) and random.Random(SEED). Background
customers and the hero customers live in the same tables; hero IDs are fixed in
``data.heroes`` so the rest of the stack can hard-reference them.
"""

from __future__ import annotations

import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

from faker import Faker

from data import heroes
from data.db import cursor

SEED = 42
NUM_BACKGROUND_CUSTOMERS = 500
NUM_BACKGROUND_DEVICES = 100
NUM_BACKGROUND_MERCHANTS = 50
NUM_BACKGROUND_TRANSACTIONS = 10_000
HERO_HISTORY_DAYS = 60

MERCHANT_CATEGORIES = [
    ("5814", "Coffee Shops & Eating Places", "low"),
    ("5411", "Grocery Stores", "low"),
    ("5912", "Drug Stores & Pharmacies", "low"),
    ("5541", "Service Stations (Fuel)", "low"),
    ("4111", "Local & Suburban Transit", "low"),
    ("5311", "Department Stores", "low"),
    ("5309", "Duty-Free Stores", "medium"),
    ("5815", "Digital Goods & Software Subscriptions", "low"),
    ("4511", "Airlines & Air Carriers", "medium"),
    ("7011", "Hotels & Lodging", "medium"),
    ("5651", "Family Clothing Stores", "medium"),
    ("5944", "Jewelry & Watches", "high"),
    ("5732", "Electronics Stores", "high"),
    ("6051", "Quasi-Cash & Crypto Exchanges", "high"),
    ("7995", "Gambling", "high"),
]

US_CITIES = [
    ("Austin", "US"), ("San Francisco", "US"), ("Seattle", "US"),
    ("New York", "US"), ("Chicago", "US"), ("Denver", "US"),
    ("Boston", "US"), ("Portland", "US"), ("Miami", "US"), ("Atlanta", "US"),
]

DEVICE_OS = ["iOS 17", "iOS 18", "Android 14", "macOS 14", "Windows 11"]
DEVICE_TYPES = ["mobile", "desktop", "tablet"]
NETWORKS = ["visa", "mastercard", "amex"]


def _apply_schema(cur) -> None:
    schema_path = Path(__file__).parent / "schema.sql"
    cur.execute(schema_path.read_text())


def _seed_categories(cur) -> None:
    cur.executemany(
        "INSERT INTO merchant_categories (code, name, risk_tier) VALUES (%s, %s, %s)",
        MERCHANT_CATEGORIES,
    )


def _seed_merchants(cur, fake: Faker, rng: random.Random) -> list[dict]:
    merchants: list[dict] = []
    # Background merchants — biased toward low-risk categories.
    weighted = (
        [c for c in MERCHANT_CATEGORIES if c[2] == "low"] * 4
        + [c for c in MERCHANT_CATEGORIES if c[2] == "medium"] * 2
        + [c for c in MERCHANT_CATEGORIES if c[2] == "high"]
    )
    for i in range(NUM_BACKGROUND_MERCHANTS):
        cat = rng.choice(weighted)
        city, country = rng.choice(US_CITIES)
        rep = rng.randint(60, 99) if cat[2] != "high" else rng.randint(25, 70)
        merchants.append({
            "merchant_id": f"merch_bg_{i:04d}",
            "name": fake.company(),
            "category_code": cat[0],
            "country": country,
            "city": city,
            "reputation_score": rep,
        })
    # Hero trigger merchants — stable IDs so trigger inserts always succeed.
    for spec in heroes.TRIGGERS.values():
        merchants.append({
            "merchant_id": spec.merchant_id,
            "name": spec.merchant_name,
            "category_code": spec.merchant_category,
            "country": spec.merchant_country,
            "city": spec.merchant_city,
            "reputation_score": 50,
        })
    # Plus a couple of recurring travel/luxury merchants used by Jane's history,
    # and the SFO departure-arc merchants for her last-72h cluster.
    merchants.extend([
        {"merchant_id": "merch_global_airways", "name": "Global Airways",
         "category_code": "4511", "country": "US", "city": "San Francisco",
         "reputation_score": 90},
        {"merchant_id": "merch_marina_bay_hotel", "name": "Marina Bay Sands",
         "category_code": "7011", "country": "SG", "city": "Singapore",
         "reputation_score": 92},
        {"merchant_id": "merch_orchard_cafe", "name": "Orchard Cafe",
         "category_code": "5814", "country": "SG", "city": "Singapore",
         "reputation_score": 85},
        {"merchant_id": "merch_rideshare", "name": "RideNow Rideshare",
         "category_code": "4111", "country": "US", "city": "San Francisco",
         "reputation_score": 87},
        {"merchant_id": "merch_sfo_cafe", "name": "SFO Terminal Cafe",
         "category_code": "5814", "country": "US", "city": "San Francisco",
         "reputation_score": 88},
        {"merchant_id": "merch_sfo_dutyfree", "name": "SFO International Duty-Free",
         "category_code": "5309", "country": "US", "city": "San Francisco",
         "reputation_score": 84},
        {"merchant_id": "merch_sfo_lounge", "name": "SFO Skyline Lounge",
         "category_code": "5814", "country": "US", "city": "San Francisco",
         "reputation_score": 86},
        # Mike's pattern-of-life merchants (Austin).
        {"merchant_id": "merch_heb_austin", "name": "H-E-B",
         "category_code": "5411", "country": "US", "city": "Austin",
         "reputation_score": 92},
        {"merchant_id": "merch_tacodeli", "name": "Tacodeli",
         "category_code": "5814", "country": "US", "city": "Austin",
         "reputation_score": 89},
        {"merchant_id": "merch_shell_austin", "name": "Shell",
         "category_code": "5541", "country": "US", "city": "Austin",
         "reputation_score": 88},
        {"merchant_id": "merch_spotify", "name": "Spotify",
         "category_code": "5815", "country": "US", "city": "Austin",
         "reputation_score": 90},
        # Alex's quiet US-only baseline merchants (San Francisco).
        {"merchant_id": "merch_bluebottle", "name": "Blue Bottle Coffee",
         "category_code": "5814", "country": "US", "city": "San Francisco",
         "reputation_score": 91},
        {"merchant_id": "merch_bart", "name": "BART",
         "category_code": "4111", "country": "US", "city": "San Francisco",
         "reputation_score": 93},
        {"merchant_id": "merch_wholefoods_sf", "name": "Whole Foods Market",
         "category_code": "5411", "country": "US", "city": "San Francisco",
         "reputation_score": 92},
        {"merchant_id": "merch_github", "name": "GitHub",
         "category_code": "5815", "country": "US", "city": "San Francisco",
         "reputation_score": 90},
        {"merchant_id": "merch_sightglass", "name": "Sightglass Coffee",
         "category_code": "5814", "country": "US", "city": "San Francisco",
         "reputation_score": 89},
        {"merchant_id": "merch_tartine", "name": "Tartine Bakery",
         "category_code": "5814", "country": "US", "city": "San Francisco",
         "reputation_score": 90},
        {"merchant_id": "merch_apple_sf", "name": "Apple Store",
         "category_code": "5311", "country": "US", "city": "San Francisco",
         "reputation_score": 95},
    ])
    cur.executemany(
        """INSERT INTO merchants (merchant_id, name, category_code, country, city, reputation_score)
           VALUES (%(merchant_id)s, %(name)s, %(category_code)s, %(country)s, %(city)s, %(reputation_score)s)""",
        merchants,
    )
    return merchants


def _seed_customers(cur, fake: Faker, rng: random.Random) -> list[dict]:
    customers: list[dict] = []
    # Hero customers first so their IDs always exist.
    for hero in heroes.HEROES.values():
        customers.append({
            "customer_id": hero.customer_id,
            "name": hero.name,
            "email": hero.email,
            "home_country": hero.home_country,
            "home_city": hero.home_city,
            "created_at": datetime(2024, 1, 1, tzinfo=timezone.utc),
        })
    for i in range(NUM_BACKGROUND_CUSTOMERS):
        city, country = rng.choice(US_CITIES)
        customers.append({
            "customer_id": f"cust_bg_{i:04d}",
            "name": fake.name(),
            "email": fake.unique.email(),
            "home_country": country,
            "home_city": city,
            "created_at": fake.date_time_between(
                start_date="-3y", end_date="-1y", tzinfo=timezone.utc
            ),
        })
    cur.executemany(
        """INSERT INTO customers (customer_id, name, email, home_country, home_city, created_at)
           VALUES (%(customer_id)s, %(name)s, %(email)s, %(home_country)s, %(home_city)s, %(created_at)s)""",
        customers,
    )
    return customers


def _seed_accounts_cards(cur, customers: list[dict], rng: random.Random) -> tuple[list[dict], list[dict]]:
    accounts: list[dict] = []
    cards: list[dict] = []
    hero_ids = {h.customer_id for h in heroes.HEROES.values()}
    for hero in heroes.HEROES.values():
        accounts.append({
            "account_id": hero.account_id, "customer_id": hero.customer_id,
            "account_type": "checking", "currency": "USD",
            "balance": 5200.00, "opened_at": datetime(2024, 1, 1, tzinfo=timezone.utc),
        })
        cards.append({
            "card_id": hero.card_id, "account_id": hero.account_id,
            "last4": hero.card_last4, "network": "visa", "status": "active",
            "issued_at": datetime(2024, 1, 1, tzinfo=timezone.utc),
        })
    for c in customers:
        if c["customer_id"] in hero_ids:
            continue
        acct_id = f"acct_{c['customer_id']}"
        card_id = f"card_{c['customer_id']}"
        accounts.append({
            "account_id": acct_id, "customer_id": c["customer_id"],
            "account_type": "checking", "currency": "USD",
            "balance": round(rng.uniform(150, 12000), 2),
            "opened_at": c["created_at"],
        })
        cards.append({
            "card_id": card_id, "account_id": acct_id,
            "last4": f"{rng.randint(0, 9999):04d}",
            "network": rng.choice(NETWORKS), "status": "active",
            "issued_at": c["created_at"],
        })
    cur.executemany(
        """INSERT INTO accounts (account_id, customer_id, account_type, currency, balance, opened_at)
           VALUES (%(account_id)s, %(customer_id)s, %(account_type)s, %(currency)s, %(balance)s, %(opened_at)s)""",
        accounts,
    )
    cur.executemany(
        """INSERT INTO cards (card_id, account_id, last4, network, status, issued_at)
           VALUES (%(card_id)s, %(account_id)s, %(last4)s, %(network)s, %(status)s, %(issued_at)s)""",
        cards,
    )
    return accounts, cards


def _seed_devices(cur, customers: list[dict], fake: Faker, rng: random.Random) -> list[dict]:
    devices: list[dict] = []
    now = datetime.now(timezone.utc)
    for hero in heroes.HEROES.values():
        devices.append({
            "device_id": hero.primary_device_id, "customer_id": hero.customer_id,
            "device_type": "mobile" if "iphone" in hero.primary_device_id else "desktop",
            "os": "iOS 18" if "iphone" in hero.primary_device_id else "macOS 14",
            "fingerprint": hero.device_fingerprint, "country": hero.device_country,
            "first_seen": now - timedelta(days=180), "last_seen": now - timedelta(hours=6),
        })
    # Jane carries a second long-known device (her work MacBook) so the
    # chatbot's get_devices_for_customer call surfaces a non-trivial list
    # rather than a one-line answer.
    devices.append({
        "device_id": "dev_jane_macbook", "customer_id": heroes.JANE.customer_id,
        "device_type": "desktop", "os": "macOS 14",
        "fingerprint": "fp_jane_macbook_pro", "country": "US",
        "first_seen": now - timedelta(days=240), "last_seen": now - timedelta(hours=20),
    })
    bg_customers = [c for c in customers if c["customer_id"] not in {h.customer_id for h in heroes.HEROES.values()}]
    for i in range(NUM_BACKGROUND_DEVICES):
        owner = rng.choice(bg_customers)
        first_seen = fake.date_time_between(start_date="-2y", end_date="-1d", tzinfo=timezone.utc)
        devices.append({
            "device_id": f"dev_bg_{i:04d}", "customer_id": owner["customer_id"],
            "device_type": rng.choice(DEVICE_TYPES), "os": rng.choice(DEVICE_OS),
            "fingerprint": fake.sha1()[:24], "country": owner["home_country"],
            "first_seen": first_seen,
            "last_seen": fake.date_time_between(start_date=first_seen, end_date="now", tzinfo=timezone.utc),
        })
    cur.executemany(
        """INSERT INTO devices (device_id, customer_id, device_type, os, fingerprint, country, first_seen, last_seen)
           VALUES (%(device_id)s, %(customer_id)s, %(device_type)s, %(os)s, %(fingerprint)s, %(country)s, %(first_seen)s, %(last_seen)s)""",
        devices,
    )
    return devices



def _tx_row(tx_id, customer_id, account_id, card_id, merchant, device_id,
            amount, currency, country, city, is_foreign, is_card_present, ts):
    return {
        "transaction_id": tx_id, "customer_id": customer_id,
        "account_id": account_id, "card_id": card_id,
        "merchant_id": merchant["merchant_id"], "device_id": device_id,
        "amount": amount, "currency": currency, "country": country, "city": city,
        "is_foreign": is_foreign, "is_card_present": is_card_present,
        "status": "approved", "ts": ts,
    }


def _hero_transactions(merchants: list[dict], rng: random.Random) -> list[dict]:
    by_id = {m["merchant_id"]: m for m in merchants}
    by_cat = {}
    for m in merchants:
        by_cat.setdefault(m["category_code"], []).append(m)
    now = datetime.now(timezone.utc)
    rows: list[dict] = []

    # Mike: ~30 steady-state transactions in Austin, low-risk merchants only.
    mike_low_risk = [m for m in merchants if m["category_code"] in {"5814", "5411", "5912", "5541", "4111"}
                     and m["city"] == "Austin"]
    if not mike_low_risk:
        mike_low_risk = [m for m in merchants if m["category_code"] in {"5814", "5411", "5912"}]
    for i in range(30):
        m = rng.choice(mike_low_risk)
        ts = now - timedelta(days=rng.randint(1, HERO_HISTORY_DAYS),
                             hours=rng.randint(0, 23), minutes=rng.randint(0, 59))
        amt = round(rng.uniform(3.5, 65.0), 2)
        rows.append(_tx_row(
            f"tx_mike_{i:03d}", heroes.MIKE.customer_id, heroes.MIKE.account_id,
            heroes.MIKE.card_id, m, heroes.MIKE.primary_device_id,
            amt, "USD", "US", "Austin",
            is_foreign=False, is_card_present=True, ts=ts,
        ))

    # Mike pattern-of-life arc — dense 3-day cluster of routine Austin spend
    # (coffee 3x, grocery, lunch, gas, Spotify recurring) so the context-surface
    # chatbot can answer "what's Mike's typical spend?" with concrete patterns.
    mike_coffee = by_id["merch_mike_coffee"]
    mike_heb = by_id["merch_heb_austin"]
    mike_tacodeli = by_id["merch_tacodeli"]
    mike_shell = by_id["merch_shell_austin"]
    mike_spotify = by_id["merch_spotify"]
    mike_arc = [
        # (suffix, merchant, amount, hours_ago)
        ("coffee_1", mike_coffee,    5.50, 66),
        ("grocery",  mike_heb,      42.00, 66),
        ("coffee_2", mike_coffee,    5.50, 42),
        ("lunch",    mike_tacodeli, 14.25, 42),
        ("gas",      mike_shell,    38.00, 42),
        ("coffee_3", mike_coffee,    5.50, 18),
        ("spotify",  mike_spotify,  10.99,  2),
    ]
    for suffix, m, amt, hrs in mike_arc:
        ts = now - timedelta(hours=hrs)
        rows.append(_tx_row(
            f"tx_mike_arc_{suffix}", heroes.MIKE.customer_id, heroes.MIKE.account_id,
            heroes.MIKE.card_id, m, heroes.MIKE.primary_device_id,
            amt, "USD", "US", "Austin",
            is_foreign=False, is_card_present=True, ts=ts,
        ))

    # Jane: travel-heavy history — past airline + hotel bookings + a few SGD spends.
    jane_airline = by_id["merch_global_airways"]
    jane_hotel = by_id["merch_marina_bay_hotel"]
    jane_cafe = by_id["merch_orchard_cafe"]
    jane_us_low = [m for m in merchants if m["category_code"] in {"5814", "5411", "5912"}
                   and m["city"] == "San Francisco"]
    if not jane_us_low:
        jane_us_low = [m for m in merchants if m["category_code"] in {"5814", "5411"}]
    # 4 historical travel bookings (airline + hotel).
    for i, (m, amt, cur_) in enumerate([
        (jane_airline, 1840.00, "USD"),
        (jane_hotel, 720.00, "SGD"),
        (jane_airline, 1620.00, "USD"),
        (jane_hotel, 540.00, "SGD"),
    ]):
        ts = now - timedelta(days=70 - i * 12, hours=rng.randint(0, 23))
        rows.append(_tx_row(
            f"tx_jane_travel_{i:02d}", heroes.JANE.customer_id, heroes.JANE.account_id,
            heroes.JANE.card_id, m, heroes.JANE.primary_device_id,
            amt, cur_, m["country"], m["city"],
            is_foreign=(cur_ != "USD"), is_card_present=False, ts=ts,
        ))
    # 6 foreign-currency spends (SGD cafes) showing past Singapore activity.
    for i in range(6):
        ts = now - timedelta(days=rng.randint(35, 90), hours=rng.randint(8, 22))
        amt = round(rng.uniform(8.0, 45.0), 2)
        rows.append(_tx_row(
            f"tx_jane_sgd_{i:02d}", heroes.JANE.customer_id, heroes.JANE.account_id,
            heroes.JANE.card_id, jane_cafe, heroes.JANE.primary_device_id,
            amt, "SGD", "SG", "Singapore",
            is_foreign=True, is_card_present=True, ts=ts,
        ))
    # 20 routine US spends so her baseline isn't only foreign tx.
    for i in range(20):
        m = rng.choice(jane_us_low)
        ts = now - timedelta(days=rng.randint(1, HERO_HISTORY_DAYS),
                             hours=rng.randint(0, 23))
        amt = round(rng.uniform(4.0, 90.0), 2)
        rows.append(_tx_row(
            f"tx_jane_us_{i:02d}", heroes.JANE.customer_id, heroes.JANE.account_id,
            heroes.JANE.card_id, m, heroes.JANE.primary_device_id,
            amt, "USD", "US", "San Francisco",
            is_foreign=False, is_card_present=True, ts=ts,
        ))

    # Jane departure arc — dense 3-day cluster (T-72h..T-2h) that plants the
    # "she's flying to Singapore" narrative for the context-surface chatbot:
    # recent airline + foreign-hotel bookings are forward geo signals, then
    # rideshare + airport spend traces her physical path to SFO.
    sf_coffee = next(
        (m for m in jane_us_low if m["category_code"] == "5814"), jane_us_low[0]
    )
    sf_grocery = next(
        (m for m in jane_us_low if m["category_code"] == "5411"), jane_us_low[0]
    )
    jane_rideshare = by_id["merch_rideshare"]
    jane_sfo_cafe = by_id["merch_sfo_cafe"]
    jane_sfo_dutyfree = by_id["merch_sfo_dutyfree"]
    jane_sfo_lounge = by_id["merch_sfo_lounge"]
    departure_arc = [
        # (suffix, merchant, amount, currency, country, city, is_foreign, is_card_present, hours_ago)
        ("coffee",     sf_coffee,         5.25, "USD", "US", "San Francisco", False, True,  72),
        ("airline",    jane_airline,   2140.00, "USD", "US", "San Francisco", False, False, 50),
        ("hotel",      jane_hotel,      680.00, "SGD", "SG", "Singapore",     True,  False, 48),
        ("grocery",    sf_grocery,       45.30, "USD", "US", "San Francisco", False, True,  30),
        ("rideshare",  jane_rideshare,   87.00, "USD", "US", "San Francisco", False, False, 12),
        ("sfo_cafe",   jane_sfo_cafe,    18.00, "USD", "US", "San Francisco", False, True,   6),
        ("sfo_duty",   jane_sfo_dutyfree, 340.00,"USD", "US", "San Francisco", False, True,  4),
        ("sfo_lounge", jane_sfo_lounge,  58.00, "USD", "US", "San Francisco", False, True,   2),
    ]
    for suffix, m, amt, cur_, country, city, is_foreign, cp, hrs in departure_arc:
        ts = now - timedelta(hours=hrs)
        rows.append(_tx_row(
            f"tx_jane_arc_{suffix}", heroes.JANE.customer_id, heroes.JANE.account_id,
            heroes.JANE.card_id, m, heroes.JANE.primary_device_id,
            amt, cur_, country, city,
            is_foreign=is_foreign, is_card_present=cp, ts=ts,
        ))

    # Alex: ~25 clean US-only tx, never high-risk, never foreign — so the trigger
    # really does introduce a new device + new country + new high-risk category.
    alex_safe = [m for m in merchants if m["category_code"] in {"5814", "5411", "5912", "5541", "4111", "5311"}
                 and m["country"] == "US" and m["category_code"] != "5732"]
    for i in range(25):
        m = rng.choice(alex_safe)
        ts = now - timedelta(days=rng.randint(1, HERO_HISTORY_DAYS),
                             hours=rng.randint(0, 23))
        amt = round(rng.uniform(5.0, 120.0), 2)
        rows.append(_tx_row(
            f"tx_alex_{i:03d}", heroes.ALEX.customer_id, heroes.ALEX.account_id,
            heroes.ALEX.card_id, m, heroes.ALEX.primary_device_id,
            amt, "USD", m["country"], m["city"],
            is_foreign=False, is_card_present=True, ts=ts,
        ))

    # Alex quiet baseline arc — dense 3-day cluster of SF-only, card-present
    # (except the one recurring GitHub sub) spend on his primary device, so the
    # trigger BR-electronics charge lands as a maximally jarring anomaly across
    # device, country, category, and card-present axes simultaneously.
    alex_bluebottle = by_id["merch_bluebottle"]
    alex_bart = by_id["merch_bart"]
    alex_wholefoods = by_id["merch_wholefoods_sf"]
    alex_github = by_id["merch_github"]
    alex_sightglass = by_id["merch_sightglass"]
    alex_tartine = by_id["merch_tartine"]
    alex_apple = by_id["merch_apple_sf"]
    alex_arc = [
        # (suffix, merchant, amount, is_card_present, hours_ago)
        ("bluebottle", alex_bluebottle,  5.00, True,  70),
        ("bart_1",     alex_bart,        4.10, True,  68),
        ("wholefoods", alex_wholefoods, 87.40, True,  50),
        ("github",     alex_github,     10.00, False, 50),
        ("sightglass", alex_sightglass,  6.25, True,  30),
        ("tartine",    alex_tartine,    14.00, True,  30),
        ("apple",      alex_apple,      98.00, True,  18),
        ("bart_2",     alex_bart,        4.10, True,   2),
    ]
    for suffix, m, amt, cp, hrs in alex_arc:
        ts = now - timedelta(hours=hrs)
        rows.append(_tx_row(
            f"tx_alex_arc_{suffix}", heroes.ALEX.customer_id, heroes.ALEX.account_id,
            heroes.ALEX.card_id, m, heroes.ALEX.primary_device_id,
            amt, "USD", "US", "San Francisco",
            is_foreign=False, is_card_present=cp, ts=ts,
        ))
    return rows


def _background_transactions(customers, accounts, cards, devices, merchants, rng):
    hero_ids = {h.customer_id for h in heroes.HEROES.values()}
    bg_accounts = [a for a in accounts if a["customer_id"] not in hero_ids]
    accounts_by_cust = {a["customer_id"]: a for a in bg_accounts}
    cards_by_acct = {c["account_id"]: c for c in cards}
    devices_by_cust: dict[str, list[str]] = {}
    for d in devices:
        if d["customer_id"] in hero_ids:
            continue
        devices_by_cust.setdefault(d["customer_id"], []).append(d["device_id"])
    bg_customers = [c for c in customers if c["customer_id"] not in hero_ids
                    and c["customer_id"] in devices_by_cust]
    if not bg_customers:
        return []
    now = datetime.now(timezone.utc)
    rows = []
    for i in range(NUM_BACKGROUND_TRANSACTIONS):
        c = rng.choice(bg_customers)
        acct = accounts_by_cust[c["customer_id"]]
        card = cards_by_acct[acct["account_id"]]
        dev_id = rng.choice(devices_by_cust[c["customer_id"]])
        m = rng.choice(merchants)
        ts = now - timedelta(days=rng.randint(1, 90),
                             hours=rng.randint(0, 23), minutes=rng.randint(0, 59))
        amt = round(rng.uniform(2.0, 350.0), 2)
        is_foreign = m["country"] != c["home_country"]
        rows.append(_tx_row(
            f"tx_bg_{i:05d}", c["customer_id"], acct["account_id"], card["card_id"],
            m, dev_id, amt, "USD" if not is_foreign else m["country"],
            m["country"], m["city"], is_foreign, rng.random() > 0.3, ts,
        ))
    return rows


def _seed_memory(cur) -> None:
    cur.execute(
        "INSERT INTO customer_memory_seed (customer_id, memory_json) VALUES (%s, %s)",
        (heroes.JANE.customer_id, json.dumps(heroes.JANE_MEMORY_SEED)),
    )


def main() -> None:
    fake = Faker()
    Faker.seed(SEED)
    rng = random.Random(SEED)
    with cursor() as (conn, cur):
        _apply_schema(cur)
        _seed_categories(cur)
        merchants = _seed_merchants(cur, fake, rng)
        customers = _seed_customers(cur, fake, rng)
        accounts, cards = _seed_accounts_cards(cur, customers, rng)
        devices = _seed_devices(cur, customers, fake, rng)
        all_tx = _hero_transactions(merchants, rng) + _background_transactions(
            customers, accounts, cards, devices, merchants, rng
        )
        cur.executemany(
            """INSERT INTO transactions
               (transaction_id, customer_id, account_id, card_id, merchant_id, device_id,
                amount, currency, country, city, is_foreign, is_card_present, status, ts)
               VALUES (%(transaction_id)s, %(customer_id)s, %(account_id)s, %(card_id)s,
                       %(merchant_id)s, %(device_id)s, %(amount)s, %(currency)s,
                       %(country)s, %(city)s, %(is_foreign)s, %(is_card_present)s,
                       %(status)s, %(ts)s)""",
            all_tx,
        )
        _seed_memory(cur)
        print(f"seeded: customers={len(customers)} merchants={len(merchants)} "
              f"accounts={len(accounts)} cards={len(cards)} devices={len(devices)} "
              f"transactions={len(all_tx)}")


if __name__ == "__main__":
    main()
