# README screenshots (first captured 2026-11-19, refreshed 2026-11-24)

Refreshed on 2026-11-24 from a throwaway stack built from `main` at c3d285e (first captured from the local development stack after 063074a),
in a separate demo account with 13 fictional household documents. Every company, person, and address is invented.

- `make_docs.py` writes the sample text PDFs (Python standard library only).
- `fill.py` signs in to an empty account and uploads and files them through the public API (OCR runs normally),
  then adds tags, senders, types, dates, and two paper-copy locations.
- `shots.mjs` captures the Library and an open document at 1440×900 (device scale 2) and the phone Library at
  390×844 (device scale 3), English, light theme. The PNGs are kept at full resolution so text stays sharp.

To regenerate (the password stays outside the repository):

```sh
python3 qa-artifacts/20261119-readme/make_docs.py /tmp/ripiano-demo-docs
RIPIANO_DEMO_PASSWORD=... uv run --no-project --with httpx python qa-artifacts/20261119-readme/fill.py http://localhost:18080 demo-readme /tmp/ripiano-demo-docs
cd apps/web && RIPIANO_DEMO_PASSWORD=... node ../../qa-artifacts/20261119-readme/shots.mjs http://localhost:18080 demo-readme ../../qa-artifacts/20261119-readme
```

Create the account first (as the owner in **People**, or with `manage.py shell` in the API container).
