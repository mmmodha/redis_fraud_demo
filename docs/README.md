# docs/

This directory holds the demo's supporting documentation. Start with
the [root README](../README.md) for the colleague-onboarding path
(`make demo` in 6 steps) and the architecture overview.

| File | Purpose |
| ---- | ------- |
| [`runbook.md`](runbook.md) | Minute-by-minute presenter script for the on-stage demo, including **Guide mode** flow and LangCache beats. |
| [`talking-points.md`](talking-points.md) | Ten quotable lines for the webinar narration. |
| [`context-retriever-setup.md`](context-retriever-setup.md) | One-time provisioning of the Redis Cloud Context Retriever surface. |
| [`agent-memory.md`](agent-memory.md) | Agent Memory schema and seeded fixtures. |
| [`architecture.excalidraw`](architecture.excalidraw) | Editable architecture diagram (data flow + mock-vs-real toggle points). |
| [`screenshots/`](screenshots/) | Hero shots embedded by the README and runbook. |

## In-app features documented here

| Feature | Where to read |
| ------- | ------------- |
| **Guide mode** | [`runbook.md` → Guide mode](runbook.md#guide-mode-in-app-navigation) — paced walkthrough with IRIS diagrams in the side panel. |
| **LangCache savings** | [`runbook.md` → LangCache](runbook.md#langcache-token-savings-chatbot) — chat paraphrase hits + verdict replay. |
| **How IRIS works** | Top-bar tab in the UI; same Lottie animations appear in Guide mode on capability steps. |
