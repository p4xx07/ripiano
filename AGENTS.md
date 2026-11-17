# Instructions for coding agents

Read these before starting work in this repository:

1. [docs/DECISIONS.md](docs/DECISIONS.md) — decisions agreed with the owner (AI via MCP only, RAG, gateway on the Raspberry Pi, S3/Drive import) and the remaining work list. It overrides older planning text where they conflict.
2. The newest `docs/HANDOFF_*.md` — how to run the tests, the local stack, and browser journeys.
3. [docs/FEATURE_PARITY.md](docs/FEATURE_PARITY.md) and [docs/IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md) — the parity contract and gates.

Rules:

- Work on branch `codex/initial-implementation`; never merge into `main`.
- Never add AI co-author or attribution lines to commits or PRs.
- Each feature slice gets tests, README/parity updates, and an independent review recorded in `.omo/evidence/`.
- Keep the Synology NAS light: if a change adds noticeable image size, RAM, or CPU load, report it to the owner before continuing.
