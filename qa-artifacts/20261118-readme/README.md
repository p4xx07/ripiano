# README screenshots (2026-11-18)

Taken from commit 27e4905 on a fresh local stack with six synthetic documents (no real personal data):
`make_docs.py` renders the sample scans, `fill.py` uploads and files them through the public API (OCR runs
normally), and `shots.mjs` signs in and captures the Library and a document at 1440×900 and 390×844 in English,
light theme. The account password is generated per run and never stored here.
