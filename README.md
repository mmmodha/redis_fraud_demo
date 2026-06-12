# Fraud Command Center

![Next.js](https://img.shields.io/badge/Next.js-15-black?logo=next.js)
![FastAPI](https://img.shields.io/badge/FastAPI-Python%203.12-009688?logo=fastapi)
![Redis](https://img.shields.io/badge/Redis-IRIS-DC382D?logo=redis)
![Anthropic Claude](https://img.shields.io/badge/Anthropic-Claude%20Sonnet-D97757?logo=anthropic)
![License](https://img.shields.io/badge/license-Apache%202.0-blue)

A narrative, sub-second fraud-detection demo: a Claude-powered agent
uses **Redis IRIS** (RDI, Feature Store, Context Retriever, Agent
Memory) to approve or block card transactions while you watch. It is
aimed at banking architects and AI teams who want to see the four IRIS
surfaces working together in one running stack, not a slide deck.
Audiences see three hero customers — one auto-approved, one
near-miss recovered by context, one blocked — each decision rendered
live alongside the Redis keys, vector searches, and tool calls that
produced it.

## Hero moments

| Mike — auto-approve | Jane — near-miss recovered | Alex — fraud blocked |
| ------------------- | -------------------------- | -------------------- |
| ![Mike auto-approve](docs/screenshots/hero-mike.png) | ![Jane review](docs/screenshots/hero-jane.png) | ![Alex blocked](docs/screenshots/hero-alex.png) |
| Feature Store answers in ~50 ms; no human, no LLM. | Agent Memory + Context Retriever flip a "block" into an "approve" in <1 s. | High-risk features + policy match → block, with the Redis evidence trail. |

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
| Mock-Claude (auto-selected)                 | Canned per-hero SSE traces with realistic latency — no Anthropic key. |
| Synthetic Postgres + RDI-emulator           | Seeded automatically; no external DB. |

| Opt-in (presenter / on-stage) | When to use it |
| ----------------------------- | -------------- |
| **Redis Cloud** (`REDIS_URL`) | Show the live IRIS surfaces in the Redis Cloud console alongside the demo UI. |
| **Anthropic API key** (`ANTHROPIC_API_KEY`) | Real Claude Sonnet tool-use instead of the canned trace. |
| **Context Retriever admin key** (`CTX_ADMIN_KEY`) | Provision the managed Context Retriever surface for the on-stage path. |

Toggling between bundled and opt-in is one env var at a time. See
[Architecture](#architecture) for where each toggle takes effect.

---

## Quick start (5 steps)

```bash
# 1. Clone
git clone <repo-url> fraud-command-center && cd fraud-command-center

# 2. Create your .env — leave every value blank for the zero-account demo
cp .env.example .env

# 3. Build, start, seed, open the UI
make demo

# 4. Open the URL the previous step printed (also auto-opens on macOS / Linux)
#    http://localhost:3000

# 5. Click any of the three hero customer cards on the dashboard.
```

That's it. `make demo` is idempotent — rerun it any time to bring the
stack back to a clean, seeded state.

To go from the bundled path to the on-stage path, fill in `REDIS_URL`,
`ANTHROPIC_API_KEY`, and (optionally) `CTX_ADMIN_KEY` in `.env`, then
run `make demo` again. Every variable is documented inline in
[`.env.example`](.env.example) with its "blank fallback" behaviour.

---

## Run-of-show

**Open with the dashboard.** Three hero cards sit side-by-side: Mike
(green — all clear), Jane (amber — needs sub-second review), Alex
(red — blocked). A live transaction feed scrolls beneath them. The
shape of the screen tells the story before anyone says a word.

**Click each hero in turn.** Each click drops into a single customer
view with four IRIS panels (RDI lag, Feature Store keys, Context
Retriever tool calls, Agent Memory) updating in real time as the
verdict streams in. The panels are not decorations — they are the
actual Redis reads and tool calls that produced the verdict.

**Close with the chatbot.** A side-by-side comparison sends every
prompt through both *naive RAG* (policy docs only) and *Context
Surface* (policy docs + live IRIS context). Same Claude model. Same
policy corpus. Different context. The answers diverge on screen.

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

5. **"Why is the Claude trace identical every time?"** You are in
   mock-Claude mode (the zero-account default). Set
   `ANTHROPIC_API_KEY` in `.env` and rerun `make demo` for the real
   Sonnet tool-use trace. The on-screen "Agent mode" badge in the UI
   tells you which mode is live.

---

## Architecture

📐 Editable diagram: [`docs/architecture.excalidraw`](docs/architecture.excalidraw) — open in [excalidraw.com](https://excalidraw.com/).

```
Postgres (synthetic core banking)
  └── RDI-emulator ──► Redis (bundled redis-stack OR Redis Cloud)
                         ├── Feature Store      (Hash / JSON per customer + card)
                         ├── Context Retriever  (managed entities + MCP-style tools)
                         ├── Agent Memory       (JSON doc per customer)
                         └── Policy / Study Index (RediSearch vector)
                                  ▲
                                  │
                  FastAPI backend ◄── Claude  (real Sonnet  ──or──  mock SSE trace)
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

The editable diagram is [`docs/architecture.excalidraw`](docs/architecture.excalidraw)
(open in [excalidraw.com](https://excalidraw.com) → File → Open).

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
