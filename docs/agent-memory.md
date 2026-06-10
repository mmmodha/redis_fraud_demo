# Agent Memory

Per-customer working memory for the fraud-detection agent. One JSON document per
customer at the canonical Redis key `mem:{customer_id}` (see the spec's key
conventions table). Owned by this task; written exclusively by the helpers in
`backend/app/agent_memory.py` and the one-shot seeder in `data/seed_memory.py`.

## Why Redis

- Sub-ms read at decision time alongside the Feature Store (same `/decide` hot path).
- Survives backend container restarts because Redis Cloud is the durable store.
- RedisJSON gives atomic `JSON.ARRAPPEND` so concurrent agent turns can append
  conversation notes without read-modify-write races.

## Schema

```jsonc
{
  "customer_id": "cust_jane",
  "travel_windows": [
    {
      "start_date": "2026-11-10",   // ISO-8601 date
      "end_date":   "2026-11-17",
      "destinations": ["Singapore"],
      "source": "chat"               // "chat" | "seed" | "agent" | "analyst"
    }
  ],
  "prior_disputes": [
    {
      "transaction_id": "tx_jane_chargeback_01",
      "reason":         "merchant_billed_twice",
      "resolution":     "refunded",
      "date":           "2026-09-04"
    }
  ],
  "flagged_devices": [
    {
      "device_id":  "dev_alex_unknown_android",
      "reason":     "first_seen_in_high_risk_geo",
      "flagged_at": "2026-06-10T19:42:11Z"
    }
  ],
  "conversation_notes": [
    {
      "timestamp": "2026-06-10T19:42:11Z",
      "text":      "Customer confirmed Singapore trip 10-17 Nov.",
      "source":    "chat"            // "chat" | "agent" | "analyst" | "seed"
    }
  ],
  "last_updated_at": "2026-06-10T19:42:11Z"
}
```

Notes:

- All four list fields are append-only audit trails. The agent never mutates
  prior entries — it appends new ones (e.g. a resolved dispute is a *new* entry
  with `resolution` filled in, not an in-place update).
- `conversation_notes` is the catch-all for analyst chat insights that don't
  fit the structured fields.
- `last_updated_at` is bumped on every write so a downstream cache can detect
  staleness cheaply.

## Helpers (`backend/app/agent_memory.py`)

All helpers take an injected `redis.Redis` client as the first argument so the
demo, the seed script, and the test suite can share one implementation.

| Helper | Behaviour |
|---|---|
| `get_memory(client, customer_id)` | Returns the JSON doc with expired travel windows filtered out. Returns a fresh empty skeleton if the key is missing — never raises on a cold customer. |
| `append_conversation_note(client, customer_id, text, source)` | Initialises the doc if absent (`JSON.SET ... NX`), then atomic `JSON.ARRAPPEND` on `$.conversation_notes`. Bumps `last_updated_at`. |
| `add_travel_window(client, customer_id, start, end, destinations, source)` | Validates dates, appends to `$.travel_windows`. |
| `add_dispute(client, customer_id, transaction_id, reason, resolution, date)` | Appends to `$.prior_disputes`. |
| `add_flagged_device(client, customer_id, device_id, reason)` | Appends to `$.flagged_devices` with a server-side UTC timestamp. |
| `purge_expired_travel_windows(client, customer_id=None)` | Removes travel windows whose `end_date < today`. Walks all `mem:*` keys when `customer_id` is `None`. Idempotent. |

Read-time filtering and the periodic purge both apply, so callers always see
fresh data even if the purge hasn't run yet (defence in depth).

## TTL / expiry approach

We deliberately do **not** put a Redis `EXPIRE` on the whole document — a
customer's prior disputes and flagged devices are permanent. Only travel
windows are volatile, and they have a natural `end_date` field.

Two layers of cleanup:

1. **On read** — `get_memory` filters out any `travel_windows[i]` whose
   `end_date` is strictly before today (UTC). This keeps the agent honest even
   if the periodic purge is paused.
2. **Periodic purge** — `purge_expired_travel_windows()` rewrites the
   `$.travel_windows` array in place. Wire it to a `cron`-style schedule (e.g.
   FastAPI lifespan task running once an hour) in Wave 3 when the agent
   service exists. Until then, callers can run it manually:

   ```bash
   python -c "from backend.app.agent_memory import purge_expired_travel_windows; \
              import redis, os; \
              purge_expired_travel_windows(redis.Redis.from_url(os.environ['REDIS_URL']))"
   ```

## Seeding Jane's "travelling 10-17 Nov"

The data generator (Wave 1) stored Jane's seed memory as JSONB in the
`customer_memory_seed` Postgres table. Two options were considered:

- **Via RDI** — would require an RDI job that transforms the source JSONB into
  the canonical schema. Possible, but the source schema (single
  `travel_window`, `notes[]` with tags) does not match the canonical schema
  (`travel_windows[]`, `conversation_notes[]`) one-to-one; expressing that
  transform in an RDI job adds coordination overhead with the RDI task.
- **One-shot seed script** ✅ — `python -m data.seed_memory` reads
  `customer_memory_seed`, maps to the canonical schema, and writes via
  `JSON.SET <key> $ ... NX`. Idempotent: re-running is a no-op for existing
  keys. Runs after `make seed` and after RDI's initial sync (RDI does not
  touch `mem:*`).

Wired into the Makefile as `make seed-memory` (depends on `seed`).

## Restart durability

Because the store is Redis Cloud (or any persisted Redis), restarting the
backend container does not lose `mem:*` data. The tests prove this by writing
through one Redis client, discarding it, opening a fresh client against the
same server, and reading the data back.
