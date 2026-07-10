# Fraud Command Center

![Next.js](https://img.shields.io/badge/Next.js-15-black?logo=next.js)
![FastAPI](https://img.shields.io/badge/FastAPI-Python%203.12-009688?logo=fastapi)
![Redis](https://img.shields.io/badge/Redis-IRIS-DC382D?logo=redis)
![License](https://img.shields.io/badge/license-Apache%202.0-blue)

A narrative, sub-second fraud-detection demo: an LLM-powered agent uses
**Redis IRIS** (RDI, Feature Store, Context Retriever, Agent Memory) plus
**LangCache** to approve, step-up, or block card transactions while you
watch. Aimed at banking architects and AI teams who want to see the IRIS
surfaces working together in one running stack — not a slide deck.

Audiences follow four hero customers — routine approve, near-miss recovered
by context, fraud blocked, step-up OTP — each decision rendered live
alongside the Redis keys, vector searches, and tool calls that produced it.

## Hero moments

| Mike — auto-approve | Jane — near-miss recovered | Alex — fraud blocked |
| ------------------- | -------------------------- | -------------------- |
| ![Mike auto-approve](docs/screenshots/hero-mike.png) | ![Jane review](docs/screenshots/hero-jane.png) | ![Alex blocked](docs/screenshots/hero-alex.png) |
| Feature Store answers in ~50 ms; no human, no LLM. | Agent Memory + Context Retriever flip a "block" into an "approve" in <1 s. | High-risk features + policy match → block, with the Redis evidence trail. |

Sarah adds a fourth beat — **step-up auth** (OTP) for a high-value purchase
that is neither auto-approve nor block. See
[`docs/screenshots/hero-sarah-reviewed.png`](docs/screenshots/hero-sarah-reviewed.png).

The full dashboard, with all four IRIS panels visible, is in
[`docs/screenshots/command-center.png`](docs/screenshots/command-center.png).

---

## What you need

**For the bundled demo: a Docker engine. Nothing else. No accounts, no
API keys, no managed services.**

| Bundled (default) | What it gives you |
| ----------------- | ----------------- |
| Docker Desktop / Docker Engine + Compose v2 | The entire host-tooling list. |
| `redis-stack` container (auto-started)      | Redis with RediSearch + RedisJSON, locally. |
| Mock agent (auto-selected)                  | Canned per-hero SSE traces with realistic latency — no LLM API key. |
| Synthetic Postgres + RDI-emulator           | Seeded automatically; no external DB. |
| Local LangCache layer                       | Semantic cache for chat + verdict replay in Redis. |

| Opt-in (presenter / on-stage) | When to use it |
| ----------------------------- | -------------- |
| **Redis Cloud** (`REDIS_URL`) | Show the live IRIS surfaces in the Redis Cloud console alongside the demo UI. |
| **Anthropic API key** (`ANTHROPIC_API_KEY`) | Real Claude Sonnet tool-use instead of the canned trace. |
| **Context Retriever admin key** (`CTX_ADMIN_KEY`) | Provision the managed Context Retriever surface for the on-stage path. |
| **LangCache Cloud** (`LANGCACHE_*`) | Managed semantic cache instead of the local Redis fallback. |

Toggling between bundled and opt-in is one env var at a time. See
[Architecture](#architecture) for where each toggle takes effect.

### Opt-in: real Redis Cloud Context Retriever

With Redis Cloud creds in `.env`, `make demo` also auto-provisions a
Context Retriever surface in Redis Cloud (idempotent — finds-or-creates
by name).

- **Required:** `REDIS_URL` (`rediss://...`) and `CTX_ADMIN_KEY` (from
  Redis Cloud → Context Retriever → Manage admin keys).
- **Optional:** `CTX_SURFACE_NAME` — surface label so multiple colleagues
  sharing a Redis Cloud tenant don't collide. Defaults to
  `fraud-command-center`.
- **Auto-written by the bootstrap:** `CTX_SURFACE_ID` and
  `CTX_AGENT_KEY` (written straight to `.env`, never logged in
  plaintext).

```dotenv
REDIS_URL=rediss://default:<password>@<host>:<port>
CTX_ADMIN_KEY=<admin-key-from-redis-cloud>
CTX_SURFACE_NAME=mehul-fraud   # optional; default: fraud-command-center
# CTX_SURFACE_ID / CTX_AGENT_KEY are written by the bootstrap
```

Leaving `CTX_ADMIN_KEY` blank skips Context Retriever entirely (stub
mode); leaving `REDIS_URL` blank while `CTX_ADMIN_KEY` is set is an
error — `make demo` halts before touching the stack. See
[`docs/context-retriever-setup.md`](docs/context-retriever-setup.md)
for the full walkthrough.

---

## Quick start (6 steps)

```bash
# 1. Clone
git clone <repo-url> fraud-command-center && cd fraud-command-center

# 2. Preflight — verifies docker/make/git/curl + 5 GB free disk + 4 GB RAM
#    + the four host ports the demo uses. Works on a bare VM with only
#    bash installed. Exits non-zero if anything is missing, with a
#    one-line install hint per item. `make doctor` is the same thing if
#    you already have make.
bash scripts/doctor.sh

# 3. Create your .env — leave every value blank for the zero-account demo
cp .env.example .env

# 4. Build, start, seed, open the UI (re-runs doctor first; bypass with
#    SKIP_DOCTOR=1 make demo)
make demo

# 5. Open the URL the previous step printed (also auto-opens on macOS / Linux)
#    http://localhost:3000

# 6. Click any hero customer card — or toggle Guide mode for a paced walkthrough.
```

That's it. `make demo` is idempotent — rerun it any time to bring the
stack back to a clean, seeded state.

> **You do not need to generate or build the data yourself.** Postgres
> starts empty; `make demo` runs a one-shot `seeder` container that
> populates Postgres, then RDI streams it into Redis. The synthetic
> bank, the four hero customers, the 10k transactions, and the agent
> memory are all created end-to-end by `make demo`. There is no
> separate "generate data" step to run.

To go from the bundled path to the on-stage path, fill in `REDIS_URL`,
`ANTHROPIC_API_KEY`, and (optionally) `CTX_ADMIN_KEY` / `LANGCACHE_*`
in `.env`, then run `make demo` again. Every variable is documented
inline in [`.env.example`](.env.example) with its "blank fallback"
behaviour.

### What `make demo` does

`make demo` is a single script that walks the stack from empty to
demo-ready. The data-generation steps are 3–5:

1. **Build** — `docker compose build` for `backend`, `frontend`,
   `seeder`, `rdi`, `context-retriever`.
2. **Start** — bring up `postgres`, `redis-stack` (if `REDIS_URL`
   blank), `backend`, `frontend`, `rdi`. Postgres boots empty:
   `infra/postgres/init.sql` is an intentional placeholder.
3. **Seed Postgres** — `compose run --rm seeder python -m data.seed`
   applies `data/schema.sql` and generates the synthetic core-banking
   data: customers (incl. heroes Mike / Jane / Alex / Sarah), accounts,
   cards, devices, merchants, MCCs, and ~10k transactions
   (`data/seed.py`, `data/heroes.py`, `data/traffic.py`).
4. **Stream into Redis** — the `rdi` service tails Postgres logical
   replication and writes the canonical Redis keys
   (`customer:*`, `card:*`, `tx:*`, `stream:transactions`, …) per
   `infra/rdi/config/`. No manual step; it runs continuously.
5. **Seed Redis-only state** —
   `compose run --rm seeder python -m data.seed_memory` adds the
   Agent Memory JSON, disputes, and pending-review rows (these don't
   originate in Postgres). Then `scripts/policy-index.sh` builds the
   RediSearch `idx:policies` vector index from `data/policies/`.
6. **Verify + print URLs** — health-checks the backend and opens
   `http://localhost:3000`.

Every step is idempotent — rerunning `make demo` re-seeds cleanly.
`make demo-reset` additionally deletes named volumes for a true
from-scratch run. The seed pipeline lives in
[`scripts/seed.sh`](scripts/seed.sh); the synthetic generator lives in
the [`data/`](data/) package.

---

## Guide mode (self-paced tour)

Toggle **Guide mode** in the top bar for a paced educational walkthrough.
The side panel explains what Redis is doing at each step — use **Continue**
to move at your own speed.

- **Mike** — full IRIS tutorial (trace, Feature Store, Context Retriever)
- **Jane** — travel memory, analyst chatbot, LangCache on chat + verdict replay
- **Alex / Sarah** — focused fraud-block and step-up stories
- **Recap** — business summary, then **Finish tour**

Capability steps embed the same animated **How IRIS works** diagrams
(RDI, Context Retriever, Agent Memory, LangCache) shown in the top-bar
architecture tab. Guide copy is LLM-agnostic: Redis improves accuracy and
cost for whatever model the bank uses.

Full presenter script: [`docs/runbook.md`](docs/runbook.md) (Guide mode section).

---

## Run-of-show

**Open with the dashboard.** Four hero cards: Mike (routine), Jane
(near-miss), Alex (blocked), Sarah (step-up). A live transaction feed
scrolls beneath them.

**Click each hero in turn.** Each click drops into a single customer
view with four IRIS panels (RDI lag, Feature Store keys, Context
Retriever tool calls, Agent Memory) updating in real time as the
verdict streams in.

**Close with the chatbot.** A side-by-side comparison sends every
prompt through both *naive RAG* (policy docs only) and *Context
Surface* (policy docs + live IRIS context). Same LLM. Same policy
corpus. Different context. Repeat a question to show **LangCache**
token savings.

The minute-by-minute presenter script is in
[`docs/runbook.md`](docs/runbook.md); quotable lines for the webinar
are in [`docs/talking-points.md`](docs/talking-points.md).

---

## Troubleshooting top 5

1. **Port 3000 / 5432 / 6379 / 8000 already in use.** Stop whatever is
   on the host port (often a previous `make demo` half-running, or a
   local Postgres) and rerun `make demo`. `make down` cleans up the
   stack; `make demo-reset` also deletes volumes.

2. **Docker memory too low.** The stack needs ~4 GB free. On Docker
   Desktop: Settings → Resources → Memory ≥ 6 GB, then Apply &
   Restart. Symptom is the backend container OOM-killing during seed.

3. **First build is slow (5–8 minutes).** Expected. Subsequent builds
   are cached and finish in under a minute. If a wheel build hangs,
   rerun `make build` — Docker resumes from the last successful layer.

4. **Variables in `.env` look fine but nothing connects.** `.env`
   parsing is strict: no spaces around `=`, no inline comments on the
   value line, no quotes unless they are part of the value. Run
   `make demo` and watch the first few lines — it prints the resolved
   `Redis mode` and `Agent mode` so you can spot a typo immediately.

5. **"Why is the agent trace identical every time?"** You are in
   mock-agent mode (the zero-account default). Set
   `ANTHROPIC_API_KEY` in `.env` and rerun `make demo` for the real
   Sonnet tool-use trace. The on-screen "Agent mode" badge in the UI
   tells you which mode is live.

6. **Doctor preflight blocking `make demo`?** `make demo` runs
   `bash scripts/doctor.sh` first and aborts if anything required is
   missing. To bypass (e.g. you know lsof is unavailable in CI, or you
   want to test a half-broken setup), prefix with `SKIP_DOCTOR=1`:
   `SKIP_DOCTOR=1 make demo`. The doctor itself never auto-installs
   anything — it only prints one-line install hints per missing item.

---

## Architecture

📐 Editable diagram: [`docs/architecture.excalidraw`](docs/architecture.excalidraw) — open in [excalidraw.com](https://excalidraw.com/).

```
Postgres (synthetic core banking)
  └── RDI-emulator ──► Redis (bundled redis-stack OR Redis Cloud)
                         ├── Feature Store      (Hash / JSON per customer + card)
                         ├── Context Retriever  (managed entities + MCP-style tools)
                         ├── Agent Memory       (JSON doc per customer)
                         ├── LangCache layer    (local semantic cache OR LangCache Cloud)
                         └── Policy / Study Index (RediSearch vector)
                                  ▲
                                  │
                  FastAPI backend ◄── LLM agent  (real Sonnet  ──or──  mock SSE trace)
                          ▲                       ▲                    ▲
                          │                       │                    │
                  Next.js demo UI         ANTHROPIC_API_KEY      AGENT_MODE=mock
                                          (real path)            (bundled default)
```

The two **mock-vs-real toggle points** are:

- `REDIS_URL` — blank → bundled `redis-stack` container; set → Redis
  Cloud. Same RDI-emulator output, same key shapes, same code path.
- `AGENT_MODE` (auto-resolved from `ANTHROPIC_API_KEY`) — blank +
  no key → `mock`; key present → `claude`; explicit `stub` for the
  deterministic test harness. The UI badge labels which one is live.

---

## RDI-emulator honesty note

The `rdi` service in `infra/docker-compose.yml` is an **in-repo
emulator** of the managed Redis Data Integration product, not the
real RDI Helm chart. It runs a small Python processor
(`infra/rdi/processor.py`) that listens on Postgres logical
replication and writes the same canonical Redis keys (`customer:*`,
`card:*`, `tx:*`, `stream:transactions`, …) the managed product
would, using the same RDI-shaped YAML config under `infra/rdi/config/`.
This keeps the demo self-contained and a single `make demo` away from
working, but it is **not** a substitute for the production RDI
deployment story — the real product handles connectors, scaling, and
operational concerns the emulator deliberately skips.

---

## License

Released under the Apache License, Version 2.0. See [`LICENSE`](LICENSE)
for the full text.

Contributions, bug reports, and PRs welcome — see
[`CONTRIBUTING.md`](CONTRIBUTING.md) for dev setup, test commands, and
the commit-message convention.
