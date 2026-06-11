# Fraud Command Center

Sub-second fraud-detection demo built on **Redis IRIS** (RDI, Feature Store,
Context Retriever, Agent Memory) + Anthropic Claude.

## Redis Cloud setup (required)

This demo uses **Redis Cloud as the only Redis runtime** — there is no local
Redis service in `docker compose`. Before running `make demo`:

1. Create a free Redis Cloud database at https://app.redislabs.com.
2. Copy `.env.example` to `.env`.
3. Paste your database's connection string into `REDIS_URL` (format:
   `redis://default:<password>@<host>:<port>`).
4. Set `ANTHROPIC_API_KEY` to your Anthropic key.
5. Run `make demo`.

## Repo layout

| Path        | Purpose                                          |
| ----------- | ------------------------------------------------ |
| `backend/`  | FastAPI service (Claude agent, feature reads).   |
| `frontend/` | Next.js Fraud Command Center UI.                 |
| `data/`     | Synthetic banking seed scripts + SQL.            |
| `infra/`    | Docker Compose stack and RDI pipeline config.    |
| `docs/`     | Demo runbook and presenter notes.                |

## Make targets

| Target       | What it does                                          |
| ------------ | ----------------------------------------------------- |
| `make demo`  | Build + start the stack, then open the UI.            |
| `make seed`  | Run the synthetic data seed (lands in a sibling task).|
| `make logs`  | Tail all service logs.                                |
| `make down`  | Stop and remove the stack (and Postgres volume).      |
