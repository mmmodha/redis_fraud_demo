-- Synthetic core-banking schema for the fraud-detection demo.
-- Source of truth for RDI → Redis. Keep types simple so RDI handles them cleanly.

DROP TABLE IF EXISTS transactions CASCADE;
DROP TABLE IF EXISTS cards CASCADE;
DROP TABLE IF EXISTS accounts CASCADE;
DROP TABLE IF EXISTS devices CASCADE;
DROP TABLE IF EXISTS customer_memory_seed CASCADE;
DROP TABLE IF EXISTS customers CASCADE;
DROP TABLE IF EXISTS merchants CASCADE;
DROP TABLE IF EXISTS merchant_categories CASCADE;

CREATE TABLE merchant_categories (
    code TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    risk_tier TEXT NOT NULL CHECK (risk_tier IN ('low', 'medium', 'high'))
);

CREATE TABLE merchants (
    merchant_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    category_code TEXT NOT NULL REFERENCES merchant_categories(code),
    country TEXT NOT NULL,
    city TEXT NOT NULL,
    reputation_score INT NOT NULL DEFAULT 80
);

CREATE TABLE customers (
    customer_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT NOT NULL,
    home_country TEXT NOT NULL,
    home_city TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE customer_memory_seed (
    customer_id TEXT PRIMARY KEY REFERENCES customers(customer_id) ON DELETE CASCADE,
    memory_json JSONB NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE accounts (
    account_id TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL REFERENCES customers(customer_id) ON DELETE CASCADE,
    account_type TEXT NOT NULL,
    currency TEXT NOT NULL DEFAULT 'USD',
    balance NUMERIC(14, 2) NOT NULL DEFAULT 0,
    opened_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE cards (
    card_id TEXT PRIMARY KEY,
    account_id TEXT NOT NULL REFERENCES accounts(account_id) ON DELETE CASCADE,
    last4 TEXT NOT NULL,
    network TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    issued_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE devices (
    device_id TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL REFERENCES customers(customer_id) ON DELETE CASCADE,
    device_type TEXT NOT NULL,
    os TEXT NOT NULL,
    fingerprint TEXT NOT NULL,
    country TEXT NOT NULL,
    first_seen TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE transactions (
    transaction_id TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL REFERENCES customers(customer_id) ON DELETE CASCADE,
    account_id TEXT NOT NULL REFERENCES accounts(account_id) ON DELETE CASCADE,
    card_id TEXT NOT NULL REFERENCES cards(card_id) ON DELETE CASCADE,
    merchant_id TEXT NOT NULL REFERENCES merchants(merchant_id),
    device_id TEXT NOT NULL REFERENCES devices(device_id),
    amount NUMERIC(12, 2) NOT NULL,
    currency TEXT NOT NULL DEFAULT 'USD',
    country TEXT NOT NULL,
    city TEXT NOT NULL,
    is_foreign BOOLEAN NOT NULL DEFAULT FALSE,
    is_card_present BOOLEAN NOT NULL DEFAULT FALSE,
    status TEXT NOT NULL DEFAULT 'approved',
    ts TIMESTAMPTZ NOT NULL
);

CREATE INDEX idx_tx_customer_ts ON transactions (customer_id, ts DESC);
CREATE INDEX idx_tx_merchant ON transactions (merchant_id);
CREATE INDEX idx_tx_ts ON transactions (ts DESC);
CREATE INDEX idx_devices_customer ON devices (customer_id);
CREATE INDEX idx_cards_account ON cards (account_id);
CREATE INDEX idx_accounts_customer ON accounts (customer_id);
