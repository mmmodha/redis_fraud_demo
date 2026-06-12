# Contributing to Fraud Command Center

Thanks for poking at this demo. This is a webinar / sales-engineering
artifact, not a product — keep contributions narrow and aimed at making
the demo clearer, faster, or more honest about what Redis IRIS does.

## Dev setup (Docker only)

You need Docker Desktop (or any Docker engine with Compose v2). That's
the entire host-tooling list. No local Python, no local Node, no
`brew install`.

```bash
git clone <repo-url> fraud-command-center
cd fraud-command-center
cp .env.example .env       # leave every value blank for the zero-account path
make demo                  # builds, starts, seeds, opens http://localhost:3000
```

Backend code lives in `backend/`, the Next.js UI in `frontend/`, the
synthetic Postgres seed + RDI-emulator config in `data/` and `infra/rdi/`.
Edit on the host, rebuild with `make build`, restart with
`docker compose -f infra/docker-compose.yml --env-file .env up -d`.

## Tests

All tests run in containers built from the same images as `make demo`:

| Command            | What it runs                                          |
| ------------------ | ----------------------------------------------------- |
| `make test`        | Backend `pytest` suite inside the backend container.  |
| `make ui-test`     | Playwright UI suite (Chromium, headless).             |
| `make demo-verify` | End-to-end 4-hero curl regression + Playwright smoke. |

`make demo-verify` is the canonical "did I break the demo" check; run
it before opening a PR that touches the agent, the UI hero cards, or
any IRIS surface.

## PR guidelines

- **One concern per PR.** Hero-card visual tweaks and a Claude
  tool-use change are two PRs, not one.
- **Keep the zero-account path working.** If your change adds a
  required env var, add a sensible mock-fallback to `.env.example`
  and prove `make demo` still works with a blank `.env`.
- **Update the runbook.** Anything that changes what the audience
  sees on stage needs a matching edit in
  [`docs/runbook.md`](docs/runbook.md).
- **Refresh screenshots when the UI changes.** Run
  `./scripts/capture-screenshots.sh` and commit the regenerated PNGs
  under `docs/screenshots/`.
- **Don't commit secrets.** `.env` is git-ignored; double-check before
  pushing. Use `.env.example` for documenting new variables.

## Commit-message convention

Conventional Commits, lower-case scope, present-tense subject:

```
<type>(<scope>): <subject>

<optional body explaining why>
```

Types: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`, `build`.
Examples:

```
feat(agent): add Context Retriever tool to mock SSE trace
fix(ui): stop hero card flicker when verdict streams in
docs(readme): document zero-account mock-Claude path
chore(infra): bump redis-stack to 7.4.0-v0
```

Keep the subject under 72 characters. Reference the wave (e.g.
`Wave 8b`) or issue number in the body when applicable.

## Code style

- Python: follow existing `backend/` patterns. `ruff` and `mypy` run
  in CI; match the surrounding code style.
- TypeScript / React: existing `frontend/` ESLint + Prettier config
  is authoritative. Functional components, hooks, Tailwind classes.
- SQL: lower-case keywords, snake_case identifiers, two-space indent —
  consistent with `data/schema.sql`.

## Licensing

By submitting a contribution you agree it will be licensed under the
Apache License 2.0, the same terms covering the rest of the repo. See
[`LICENSE`](LICENSE).
