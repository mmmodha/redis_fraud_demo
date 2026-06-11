"""Fixed identities and scripted 'next transaction' specs for the three hero customers.

Stable IDs so later waves (Feature Store, Context Retriever, Agent Memory, UI) can
hard-reference them. Specs describe the transaction the dashboard's trigger button
inserts on demand — these are the storyboard moments from the spec note.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


HeroKey = Literal["mike", "jane", "alex", "sarah"]


@dataclass(frozen=True)
class HeroProfile:
    key: HeroKey
    customer_id: str
    name: str
    email: str
    home_country: str
    home_city: str
    account_id: str
    card_id: str
    card_last4: str
    primary_device_id: str
    device_fingerprint: str
    device_country: str


@dataclass(frozen=True)
class TriggerSpec:
    merchant_id: str
    merchant_name: str
    merchant_category: str
    merchant_country: str
    merchant_city: str
    amount: float
    currency: str
    country: str
    city: str
    is_foreign: bool
    is_card_present: bool
    # Override device — None means reuse hero's primary device.
    device_id: str | None = None
    device_country: str | None = None
    device_os: str | None = None
    device_type: str | None = None
    device_fingerprint: str | None = None
    extra_merchant: dict | None = field(default=None)


MIKE = HeroProfile(
    key="mike",
    customer_id="cust_mike",
    name="Mike Rivera",
    email="mike.rivera@example.com",
    home_country="US",
    home_city="Austin",
    account_id="acct_mike_chk",
    card_id="card_mike_visa",
    card_last4="4242",
    primary_device_id="dev_mike_iphone",
    device_fingerprint="fp_mike_iphone_15_pro",
    device_country="US",
)

JANE = HeroProfile(
    key="jane",
    customer_id="cust_jane",
    name="Jane Doe",
    email="jane.doe@example.com",
    home_country="US",
    home_city="San Francisco",
    account_id="acct_jane_chk",
    card_id="card_jane_visa",
    card_last4="7788",
    primary_device_id="dev_jane_iphone",
    device_fingerprint="fp_jane_iphone_15",
    device_country="US",
)

ALEX = HeroProfile(
    key="alex",
    customer_id="cust_alex",
    name="Alex Chen",
    email="alex.chen@example.com",
    home_country="US",
    home_city="Seattle",
    account_id="acct_alex_chk",
    card_id="card_alex_visa",
    card_last4="3344",
    primary_device_id="dev_alex_macbook",
    device_fingerprint="fp_alex_macbook_pro",
    device_country="US",
)

SARAH = HeroProfile(
    key="sarah",
    customer_id="cust_sarah",
    name="Sarah Kim",
    email="sarah.kim@example.com",
    home_country="US",
    home_city="Seattle",
    account_id="acct_sarah_chk",
    card_id="card_sarah_visa",
    card_last4="9911",
    primary_device_id="dev_sarah_iphone",
    device_fingerprint="fp_sarah_iphone_15",
    device_country="US",
)


HEROES: dict[HeroKey, HeroProfile] = {
    "mike": MIKE, "jane": JANE, "alex": ALEX, "sarah": SARAH,
}


# Triggered "next transaction" specs — match the demo storyboard in the spec note.
TRIGGERS: dict[HeroKey, TriggerSpec] = {
    "mike": TriggerSpec(
        merchant_id="merch_mike_coffee",
        merchant_name="Radio Coffee & Beer",
        merchant_category="5814",  # eating places / coffee — low risk
        merchant_country="US",
        merchant_city="Austin",
        amount=6.75,
        currency="USD",
        country="US",
        city="Austin",
        is_foreign=False,
        is_card_present=True,
    ),
    "jane": TriggerSpec(
        merchant_id="merch_jane_boutique_sg",
        merchant_name="Orchard Luxe Boutique",
        merchant_category="5651",  # apparel — luxury
        merchant_country="SG",
        merchant_city="Singapore",
        amount=480.00,
        currency="SGD",
        country="SG",
        city="Singapore",
        is_foreign=True,
        is_card_present=True,
    ),
    "alex": TriggerSpec(
        merchant_id="merch_alex_electronics_br",
        merchant_name="MegaTech Eletronicos",
        merchant_category="5732",  # electronics — high risk in our taxonomy
        merchant_country="BR",
        merchant_city="Sao Paulo",
        amount=2400.00,
        currency="USD",
        country="BR",
        city="Sao Paulo",
        is_foreign=True,
        is_card_present=False,
        device_id="dev_alex_unknown_android",
        device_country="BR",
        device_os="Android 14",
        device_type="mobile",
        device_fingerprint="fp_unknown_android_pixel",
    ),
    "sarah": TriggerSpec(
        merchant_id="merch_sarah_tiffany_ny",
        merchant_name="Tiffany & Co Manhattan",
        merchant_category="5944",  # jewelry — high risk MCC, novel for Sarah
        merchant_country="US",
        merchant_city="New York",
        amount=1450.00,
        currency="USD",
        country="US",
        city="New York",
        is_foreign=False,
        is_card_present=True,
    ),
}


JANE_MEMORY_SEED = {
    "notes": [
        {
            "text": "Customer mentioned upcoming trip: travelling 10-17 Nov to Singapore.",
            "source": "chat",
            "tags": ["travel", "singapore"],
        }
    ],
    "travel_window": {"start": "2026-11-10", "end": "2026-11-17", "destination": "Singapore"},
}


SARAH_MEMORY_SEED = {
    "notes": [
        {
            "text": (
                "Sarah's business trips skew toward dining + transit + hotels. "
                "Flag high-value retail anomalies during travel for step-up "
                "rather than block — false-blocking on her travel days has "
                "high CLV cost."
            ),
            "source": "analyst",
            "tags": ["step-up", "travel", "clv"],
        },
        {
            "text": (
                "Business trip in progress: Seattle → New York, "
                "flight booked 2 days ago, Manhattan hotel checked in yesterday."
            ),
            "source": "chat",
            "tags": ["travel", "new-york"],
        },
    ],
    "travel_window": {
        "start": "2026-06-09",
        "end": "2026-06-13",
        "destination": "New York",
    },
}
