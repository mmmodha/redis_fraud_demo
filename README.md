# Fraud Command Center

![Next.js](https://img.shields.io/badge/Next.js-15-black?logo=next.js)
![FastAPI](https://img.shields.io/badge/FastAPI-Python%203.12-009688?logo=fastapi)
![Redis IRIS](https://img.shields.io/badge/Redis-IRIS-DC382D?logo=redis)
![Anthropic Claude](https://img.shields.io/badge/Anthropic-Claude%20Sonnet-D97757?logo=anthropic)

A narrative, sub-second fraud-detection demo. A Claude-powered agent uses
**Redis IRIS** (RDI, Feature Store, Context Retriever, Agent Memory) to
walk the line between blocking real fraud and not frustrating legitimate
customers — three hero customers, one dashboard, four live IRIS panels,
all under a second per decision.

![Command Center](docs/screenshots/command-center.png)

---

## Run the demo in 5 minutes

```bash
# 1. Clone and enter the repo
git clone <repo-url> fraud-command-center && cd fraud-command-center

# 2. Configure your Redis Cloud + Anthropic credentials
cp .env.example .env
$EDITOR .env          # fill in REDIS_URL and ANTHROPIC_API_KEY

# 3. Bring up the stack and open the UI
make demo             # builds, waits for backend health, opens http://localhost:3000
```

First time only, after `make demo`:

```bash
make seed             # populate Postgres → RDI mirrors into Redis
make context-up       # bootstrap the Context Retriever surface in Redis Cloud
make policy-index     # build the policy RAG index in Redis
```

See [`docs/runbook.md`](docs/runbook.md) for the on-stage walkthrough
and [`docs/context-retriever-setup.md`](docs/context-retriever-setup.md)
for Context Retriever provisioning.

---

## Architecture

```
Postgres (synthetic core banking)
  └── RDI ──► Redis Cloud
                ├── Feature Store         (Hash / JSON per customer + card)
                ├── Context Retriever     (managed entities + MCP-style tools)
                ├── Agent Memory          (JSON doc per customer)
                └── Policy/Study Index    (RediSearch vector index;
                                           shared by BOTH RAG and IRIS pipelines)
                        ▲
                        │
        FastAPI backend (Python) ◄── Anthropic Claude
          ├── /decide   (fraud agent — IRIS only)
          └── /chat     (runs RAG + IRIS in parallel for side-by-side)
                        ▲
                        │
              Next.js demo UI (React)
```

The chatbot at the bottom of the dashboard sends every prompt through
**both** pipelines — naive RAG (policy docs only) and Context Surface
(policy docs + live IRIS context) — so the audience watches the LLM
answer change in real time. **Same model. Same policy docs. Different
context.**

![Chatbot comparison](docs/screenshots/chatbot-comparison.png)

---

## Redis Cloud setup (required)

This demo uses **Redis Cloud as the only Redis runtime** — there is no
local Redis service in `docker compose`. Before running `make demo`:

1. Create a free Redis Cloud database at <https://app.redislabs.com>
   (enable RediSearch + RedisJSON modules).
2. Copy `.env.example` to `.env`.
3. Paste your database's connection string into `REDIS_URL`
   (format: `redis://default:<password>@<host>:<port>` or
   `rediss://...` for TLS).
4. Set `ANTHROPIC_API_KEY` to your Anthropic key.
5. Run `make demo`.

For offline rehearsal (no Anthropic key available), set
`AGENT_MODE=stub` in `.env` — verdicts are deterministic and match the
live demo.

---

## Repo layout

| Path        | Purpose                                          |
| ----------- | ------------------------------------------------ |
| `backend/`  | FastAPI service (Claude agent, feature reads).   |
| `frontend/` | Next.js Fraud Command Center UI.                 |
| `data/`     | Synthetic banking seed scripts + SQL.            |
| `infra/`    | Docker Compose stack and RDI pipeline config.    |
| `docs/`     | Demo runbook, presenter notes, screenshots.      |
| `scripts/`  | Bootstrap, indexing, and screenshot capture.     |

## Make targets

| Target              | What it does                                          |
| ------------------- | ----------------------------------------------------- |
| `make demo`         | Build + start the stack, wait for health, open the UI.|
| `make seed`         | Seed Postgres with the synthetic banking data.        |
| `make seed-memory`  | Seed Agent Memory fixtures (Jane's travel window).    |
| `make context-up`   | Provision the Context Retriever surface (one-shot).   |
| `make policy-index` | Rebuild the RediSearch policy index `idx:policies`.   |
| `make rdi-status`   | Show current RDI sync lag (Postgres → Redis).         |
| `make ui-test`      | Run the Playwright smoke + screenshot suites.         |
| `make logs`         | Tail all service logs.                                |
| `make down`         | Stop and remove the stack (and Postgres volume).      |

## Capturing fresh screenshots

```bash
./scripts/capture-screenshots.sh   # re-runs the Playwright capture flow
```

Outputs land in `docs/screenshots/` and are embedded by both this README
and the presenter runbook.

---

## Presenter resources

- [`docs/runbook.md`](docs/runbook.md) — minute-by-minute stage script.
- [`docs/talking-points.md`](docs/talking-points.md) — 10 quotable lines
  for the webinar.
- [`docs/context-retriever-setup.md`](docs/context-retriever-setup.md) —
  Context Retriever bootstrap walkthrough.
- [`docs/agent-memory.md`](docs/agent-memory.md) — Agent Memory schema
  and seeded fixtures.
