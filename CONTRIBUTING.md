# Contributing

Ripiano is still under staged implementation. Before changing behavior, check [the feature parity contract](docs/FEATURE_PARITY.md) and [implementation plan](docs/IMPLEMENTATION_PLAN.md). A change to a Paperless baseline capability should include a concrete API or user journey that proves the intended behavior.

Keep personal documents, agent tokens, Telegram bot tokens, NAS paths, and backup snapshots out of Git. Use synthetic fixtures for tests and screenshots. Preserve imported originals and make derived files rebuildable.

For a local check, run the relevant API tests, web build, Android debug build, and Compose config validation described in [README.md](README.md). A deployment or backup change also needs a restore check. Record the exact checks in the PR description, including any unavailable real-device or NAS validation.
