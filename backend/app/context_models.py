"""Context Retriever entity models for the Fraud Command Center demo.

One :class:`ContextModel` subclass per canonical Redis key family (the same
families RDI writes from Postgres — see ``infra/rdi/config/jobs/*.yaml``).

Field names match exactly what RDI emits into the JSON documents (confirmed
via ``JSON.GET`` against the live Redis Cloud database for the three hero
customers). Don't rename them here unless you also retrain RDI.

Timestamp fields (``created_at``, ``opened_at``, ``issued_at``, ``first_seen``,
``last_seen``, ``ts``) arrive as ISO-8601 strings rather than epoch numerics,
so they're declared as ``text`` indexes — Context Retriever exposes a search
tool on them which the agent can use for "recent transactions" queries.
"""

from __future__ import annotations

from context_surfaces.context_model import ContextField, ContextModel


class Customer(ContextModel):
    __redis_key_template__ = "customer:{customer_id}"

    customer_id: str = ContextField(description="Stable customer identifier", is_key_component=True)
    name: str = ContextField(description="Full legal name", index="text")
    email: str = ContextField(description="Primary email", index="text")
    home_country: str = ContextField(description="ISO-2 home country code", index="tag")
    home_city: str = ContextField(description="Home city", index="tag")
    created_at: str = ContextField(description="ISO-8601 account creation timestamp", index="text")


class Account(ContextModel):
    __redis_key_template__ = "account:{account_id}"

    account_id: str = ContextField(description="Account identifier", is_key_component=True)
    customer_id: str = ContextField(description="Owning customer", index="tag")
    account_type: str = ContextField(description="checking / savings / credit", index="tag")
    currency: str = ContextField(description="ISO-4217 account currency", index="tag")
    balance: float = ContextField(description="Current balance in account currency", index="numeric")
    opened_at: str = ContextField(description="ISO-8601 open timestamp", index="text")


class Card(ContextModel):
    __redis_key_template__ = "card:{card_id}"

    card_id: str = ContextField(description="Card identifier", is_key_component=True)
    account_id: str = ContextField(description="Associated account", index="tag")
    last4: str = ContextField(description="Last 4 PAN digits", index="tag")
    network: str = ContextField(description="visa / mastercard / amex", index="tag")
    status: str = ContextField(description="active / blocked / closed", index="tag")
    issued_at: str = ContextField(description="ISO-8601 issuance timestamp", index="text")


class Device(ContextModel):
    __redis_key_template__ = "device:{device_id}"

    device_id: str = ContextField(description="Device identifier", is_key_component=True)
    customer_id: str = ContextField(description="Customer this device belongs to", index="tag")
    device_type: str = ContextField(description="mobile / desktop / tablet", index="tag")
    os: str = ContextField(description="Operating system + version", index="text")
    fingerprint: str = ContextField(description="Stable device fingerprint", index="text")
    country: str = ContextField(description="ISO-2 country last seen from", index="tag")
    first_seen: str = ContextField(description="ISO-8601 first observation", index="text")
    last_seen: str = ContextField(description="ISO-8601 last observation", index="text")


class MerchantCategory(ContextModel):
    """MCC catalogue. Note: RDI writes the key column ``code``, not ``mcc_id``."""

    __redis_key_template__ = "mcc:{code}"

    code: str = ContextField(description="Merchant category code", is_key_component=True)
    name: str = ContextField(description="Human-readable category name", index="text")
    risk_tier: str = ContextField(description="low / medium / high fraud risk", index="tag")


class Merchant(ContextModel):
    """Merchant directory. RDI writes ``category_code`` (not ``mcc_id``) for the FK to MerchantCategory."""

    __redis_key_template__ = "merchant:{merchant_id}"

    merchant_id: str = ContextField(description="Merchant identifier", is_key_component=True)
    name: str = ContextField(description="Merchant display name", index="text")
    category_code: str = ContextField(description="Merchant category code (FK -> mcc.code)", index="tag")
    country: str = ContextField(description="ISO-2 country", index="tag")
    city: str = ContextField(description="City", index="tag")
    reputation_score: int = ContextField(description="0-100 internal merchant reputation", index="numeric")


class Transaction(ContextModel):
    """Card transaction. The timestamp field is ``ts`` (RDI mirrors the Postgres column name)."""

    __redis_key_template__ = "tx:{transaction_id}"

    transaction_id: str = ContextField(description="Transaction identifier", is_key_component=True)
    customer_id: str = ContextField(description="Customer who initiated the transaction", index="tag")
    account_id: str = ContextField(description="Account charged", index="tag")
    card_id: str = ContextField(description="Card used", index="tag")
    merchant_id: str = ContextField(description="Merchant the transaction was with", index="tag")
    device_id: str = ContextField(description="Device the transaction originated from", index="tag")
    amount: float = ContextField(description="Transaction amount in transaction currency", index="numeric")
    currency: str = ContextField(description="ISO-4217 transaction currency", index="tag")
    country: str = ContextField(description="ISO-2 country code where the swipe happened", index="tag")
    city: str = ContextField(description="City where the swipe happened", index="tag")
    is_foreign: bool = ContextField(description="True if country != customer.home_country", index="tag")
    is_card_present: bool = ContextField(description="True for in-person swipes / dips / taps", index="tag")
    status: str = ContextField(description="approved / declined / pending", index="tag")
    ts: str = ContextField(description="ISO-8601 transaction timestamp", index="text")


CONTEXT_MODELS = (
    Customer,
    Account,
    Card,
    Device,
    MerchantCategory,
    Merchant,
    Transaction,
)
