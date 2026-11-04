# Ripiano

Ripiano is a self-hosted document archive for a NAS. It combines quick mobile capture, automatic filing, full-text search, and a simple way to locate paper originals with stickers. The web app is an installable PWA for iOS and Android. An Android client shares the web interface and adds a native document scanner.

Ripiano is an independent implementation. Paperless-ngx v3.4.2 is the capability baseline, not a backend dependency or a workflow template. The product target is feature parity with that release plus a better day-to-day filing process.

## Planning documents

- [Product specification](docs/PRODUCT_SPEC.md): users, workflows, interaction design, and acceptance criteria.
- [Feature parity](docs/FEATURE_PARITY.md): Paperless capabilities and Ripiano delivery gates.
- [Architecture](docs/ARCHITECTURE.md): services, data model, classification, agents, security, deployment, and backup.
- [Implementation plan](docs/IMPLEMENTATION_PLAN.md): build order and verification gates.

These documents are the proposed implementation baseline for review. Component versions and model choices will be pinned after the first representative benchmark. No Paperless source code is included in this repository.
