# CI job to add by hand: API suite on PostgreSQL + pgvector + zbar

The agent session is not permitted to edit `.github/`. Paste this job into `.github/workflows/verify-and-publish.yml`
under `jobs:` (next to `api:`). It runs the same suite the SQLite job runs, plus what SQLite skips: stored
full-text search with Italian/English stemming, pgvector semantic search, share-link row locks, the search-index
upgrade test, and the eight barcode-reading tests (zbar).

Verified locally on 2026-11-18 against `pgvector/pgvector:pg17`: 310 passed, 8 skipped (the 8 are the barcode
tests, skipped only because zbar is not installed on the development Mac).

```yaml
  api-postgres:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: pgvector/pgvector:pg17
        env:
          POSTGRES_USER: ripiano
          POSTGRES_PASSWORD: ci-only-password
          POSTGRES_DB: ripiano
        ports: ["5432:5432"]
        options: >-
          --health-cmd "pg_isready -U ripiano" --health-interval 5s --health-timeout 5s --health-retries 20
    steps:
      - uses: actions/checkout@v7
      - run: sudo apt-get update && sudo apt-get install -y --no-install-recommends libzbar0
      - uses: astral-sh/setup-uv@v10.3.2
        with:
          version: "0.9.26"
      - run: uv python install 3.13
      - run: uv sync --frozen --python 3.13
        working-directory: services/api
      - run: uv run pytest -q -rs
        working-directory: services/api
        env:
          RIPIANO_DEBUG: "1"
          RIPIANO_DB_HOST: localhost
          RIPIANO_DB_PASSWORD: ci-only-password
```
