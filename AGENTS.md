# Instructions for coding agents

Read these before starting work in this repository:

1. [docs/DECISIONS.md](docs/DECISIONS.md) — decisions agreed with the owner (AI via MCP only, RAG, gateway on the Raspberry Pi, S3/Drive import) and the remaining work list. It overrides older planning text where they conflict.
2. [docs/HANDOFF_2026-11-20.md](docs/HANDOFF_2026-11-20.md) — current state, verification, and release blockers.
3. [docs/FEATURE_PARITY.md](docs/FEATURE_PARITY.md) and [docs/IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md) — the parity contract and gates.

Rules:

- Work on branch `codex/initial-implementation`; merge into `main` only through a pull request when the owner asks.
- Never add AI co-author or attribution lines to commits or PRs.
- Each feature slice gets tests, README/parity updates, and an independent review recorded in `.omo/evidence/`.
- Keep the Synology NAS light: if a change adds noticeable image size, RAM, or CPU load, report it to the owner before continuing.
