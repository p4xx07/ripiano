# Formats and barcodes review

An independent read-only reviewer covered code, security, and UX, and returned **REQUEST CHANGES**: no critical or high findings, 5 medium, and 6 low. All findings were addressed before the checkpoint, except where noted.

| Severity | Finding | Resolution |
| --- | --- | --- |
| MEDIUM | Reprocessing an already filed PDF that contains a separator sheet would split and hide it. | Only a document's first processing (`processed_at is None`) can split it. Tested. |
| MEDIUM | Split parts lost email-rule filing and email origin. | Parts copy the source's sender and type (with origin), its non-rule tags, and its `DocumentEmail`. Tested. |
| MEDIUM | A trashed or failed split source was invisible in Trash and Exceptions but could be purged. | Split sources are hidden only from the normal Library views; Trash and Exceptions list them. Tested. |
| MEDIUM | A concurrent ASN change returned 500. | The ASN is written in its own savepoint, and `IntegrityError` maps to 409. |
| MEDIUM | A split failure could fail processing and leave orphan originals. | Splitting is all-or-nothing under a row lock. On failure, written part files are removed and a note is added, and the scan continues unsplit. Tested by failing on the third part. |
| LOW | No page-size limit before rasterizing. | Pages above about 40 Mpx at the scan DPI skip barcode scanning. Ghostscript keeps `-dSAFER`. |
| LOW | Separators after the page cap were ignored, yet the scan was still split. | Scans longer than `RIPIANO_BARCODE_MAX_PAGES` are never split; a note explains why. |
| LOW | HTML mail without `</head>` lost its text. | `head` is no longer skipped (`title`, `style`, and `script` still are). Tested. |
| LOW | ODF script and encryption checks were weak. | `Scripts/` and manifest `encryption-data` are refused, and the wording says "password-protected". Legacy OLE VBA is not inspected; LibreOffice runs without macro execution on an internal network. Accepted. |
| LOW | An invalid ASN input cleared the ASN, and the split link looked like a duplicate warning. | Text input with client validation and an error message. The split link has its own icon and style. |
| LOW | Splitting did not recheck Trash. | The split locks the row and skips trashed or already split sources. |

## Verification

- In the Linux ARM image with zbar and Ghostscript, `test_barcodes.py`, `test_formats.py`, and `test_mail.py` gave 35 passed. Locally without zbar, the full API suite gave 111 passed and 6 skipped (zbar-only tests and the existing PostgreSQL-only case).
- Real browser journeys passed on desktop and mobile:
  - `.doc`, `.odt`, and `.eml` conversion through the private LibreOffice converter;
  - a separator-sheet split with ASN, `asn:` search, and the full-scan link;
  - email intake.
- The full suite caught a label clash ("from" in the ASN hint matched `getByLabel("From")`). The hint was reworded, and the affected filing journeys pass.

This scoped review is not the R4/9.5 release score.
