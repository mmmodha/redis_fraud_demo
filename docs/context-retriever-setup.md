# Redis Context Retriever — Presenter Cheat Sheet

Five-minute walkthrough for getting the **Fraud Command Center** surface live in
Redis Cloud and confirming the auto-generated MCP tools are reachable from the
backend. Skip ahead to **Re-pointing a fresh laptop** if the surface already
exists and you just need a new agent key.

> **Heads-up:** `make demo` now wraps `make context-up` automatically when both
> `CTX_ADMIN_KEY` and `REDIS_URL` are set in `.env` (idempotent — re-uses the
> surface on subsequent runs). The manual `make context-up` flow below still
> works unchanged; use it when you want to provision the surface without
> rebuilding the whole stack. Set `CTX_SURFACE_NAME` in `.env` to label the
> surface (useful when sharing a Redis Cloud tenant); defaults to
> `fraud-command-center`.

---

## 1. One-time admin-key generation (Redis Cloud)

1. Sign in to <https://cloud.redis.io>.
2. Open **Context Retriever** → **Manage admin keys** → **Create admin key**.
3. Name it something obvious (`fcc-demo-admin`), copy the value once — you can't
   see it again.
4. Paste it into the repo's `.env` as `CTX_ADMIN_KEY=...`. Make sure `.env` is
   *not* committed (`.gitignore` already covers it).

Required `.env` keys before running `make context-up`:

| Key               | Source                                            |
| ----------------- | ------------------------------------------------- |
| `REDIS_URL`       | Redis Cloud DB connection string (`rediss://...`) |
| `CTX_ADMIN_KEY`   | step 3 above                                      |

The bootstrap fills in `CTX_SURFACE_ID` and `CTX_AGENT_KEY` for you.

---

## 2. `make context-up`

```bash
make context-up
```

What it does, in order (all idempotent):

1. Builds `infra/context-retriever/Dockerfile` → `fcc-context-retriever-bootstrap:local`
   (one-shot Python 3.12 image — keeps the 3.11+ SDK requirement off the host).
2. Runs the container with `.env` and `backend/app/context_models.py` mounted.
   The bootstrap script (`infra/context-retriever/bootstrap.py`):
   - Parses `REDIS_URL` for host/port/user/password (never echoes them).
   - Finds the `fraud-command-center` surface by name; creates it if missing
     using the `ContextModel` classes from `backend/app/context_models.py`.
   - Mints a fresh agent key (`fraud-agent-<pid>`).
   - Writes `CTX_SURFACE_ID`, `CTX_AGENT_KEY`, and
     `NEXT_PUBLIC_CONTEXT_RETRIEVER_URL`
     (`https://app.redislabs.com/#/context-retriever/<CTX_SURFACE_ID>`)
     back into `.env` in place.
3. Dumps the tool catalog (`ctxctl tools list --agent-key <redacted>`).
4. Calls one sample tool (`get_customer_by_id` for `cust_mike`) to prove
   end-to-end wiring works.

**Re-running is safe.** A second `make context-up` reuses the existing surface
and just writes a new agent key (and refreshes the TopBar CR URL). Old agent keys
keep working — they're never deleted by the bootstrap; rotate them in the Redis
Cloud UI if needed.

---

## 3. Confirm tools registered

Expected output from step 3 above: a 44-row table with one auto-generated tool
per `ContextField` filter, plus `get_*_by_id` and `search_*_by_text` per entity:

```
get_customer_by_id            filter_customer_by_home_country   search_customer_by_text
get_account_by_id             filter_account_by_account_type    search_account_by_text
get_card_by_id                filter_card_by_network            search_card_by_text
get_device_by_id              filter_device_by_country          search_device_by_text
get_merchant_by_id            filter_merchant_by_category_code  search_merchant_by_text
get_merchantcategory_by_id    filter_merchantcategory_by_risk_tier ...
get_transaction_by_id         filter_transaction_by_customer_id search_transaction_by_text
                              find_transaction_by_amount_range
                              find_account_by_balance_range
                              find_merchant_by_reputation_score_range
```

Open the Redis Cloud **Context Retriever** console for `fraud-command-center`
and you should see the seven entities (Customer, Account, Card, Device,
Merchant, MerchantCategory, Transaction) with row counts matching the seed.

![Context Retriever console](img/context-retriever-console.png)
*Screenshot placeholder — capture the Redis Cloud "Context Retriever → fraud-command-center" page after running `make context-up` and drop it into `docs/img/`.*

---

## 4. Re-pointing a fresh laptop at the same surface

If a colleague already provisioned the surface and just shared their `.env`
(minus secrets), only two values need to be regenerated locally:

```bash
# Drop a new CTX_ADMIN_KEY into .env, then:
make context-up
```

`context-up` detects the existing `fraud-command-center` by name, reuses its
`CTX_SURFACE_ID`, and mints a new `CTX_AGENT_KEY` for this laptop. The previous
laptop's agent key is unaffected.

To target a **different** surface name (e.g. for a staging demo, or when
sharing a Redis Cloud tenant with another colleague), set `CTX_SURFACE_NAME`
in `.env` and re-run `make context-up` (or `make demo`):

```bash
echo 'CTX_SURFACE_NAME=mehul-fraud' >> .env
make context-up
```

The bootstrap finds-or-creates by name, so a new value provisions a SECOND
surface; the original `fraud-command-center` is left untouched. The
`AGENT_NAME` constant in `infra/context-retriever/bootstrap.py` is still the
only way to change the per-agent label.

---

## 5. Sanity tests

After `make context-up` exits clean:

```bash
# Smoke tests against the live surface (one call per public method, per hero):
docker run --rm -e CTX_AGENT_KEY -v "$(pwd):/repo" -w /repo \
  --entrypoint sh python:3.12-slim \
  -c "pip install --quiet -r backend/requirements-dev.txt && \
      pytest tests/test_context_retriever_client.py -v"
```

Expected: **9 passed**. The tests skip cleanly if `CTX_AGENT_KEY` is missing or
the SDK isn't installed, so they're safe to leave in CI.

---

## Troubleshooting

| Symptom                                          | Fix                                                                                          |
| ------------------------------------------------ | -------------------------------------------------------------------------------------------- |
| `CTX_ADMIN_KEY not set in .env`                  | Generate an admin key in Redis Cloud (step 1) and paste into `.env`.                         |
| `ERROR: REDIS_URL not set in .env`               | Copy the connection string from the Redis Cloud DB page; must include user + password.       |
| Tool call returns empty `content`                | RDI may still be back-filling. Wait ~30s, re-run the sample call.                            |
| `Event loop is closed` during pytest             | You're running tests inside a non-Docker venv with the wrong async loop policy — use Docker. |
| `make context-up` builds image but then hangs    | Check Docker Desktop is running; the script needs outbound HTTPS to `cloud.redis.io`.        |
| Surface exists but tool catalog is empty         | Open Redis Cloud → Context Retriever → fraud-command-center → re-sync; takes ~10s.           |

---

## Secrets policy

Never log or echo `CTX_ADMIN_KEY`, `CTX_AGENT_KEY`, `REDIS_URL`, or
`REDIS_PASSWORD`. The bootstrap and `scripts/context-up.sh` both redact them.
If you need to share a session output, scrub the `.env` first.
