# Versions and page tools review

An independent read-only reviewer covered code, security, and UX, and returned **REQUEST CHANGES**: no critical findings, 1 high, 4 medium, and 8 low. It confirmed:
- owner scoping on every endpoint, including version download through another user's document ID;
- CSRF protection;
- version numbering under a row lock, with new uuid-named files and no overwrites;
- Ghostscript run with `-dSAFER` and an argument list;
- purge, export, and backup coverage of version files.

Separately, the primary agent found that backups refused the new `previews/` cache directory. Backups now skip it, and a test checks that backups contain version files but no previews.

| Severity | Finding | Resolution |
| --- | --- | --- |
| HIGH | After a new version failed processing, the UI blocked restoring an older version or uploading another file. | Restore and upload are enabled for `ready` and `failed` documents; page tools still need a readable PDF. Tested by restoring from a failed status. |
| MEDIUM | Encrypted or corrupt PDFs and oversize results returned 500. | The reader maps pypdf errors and password protection to `VersionError`. `InvalidDocument` from storage maps to 400. Merge errors name the document. Tested. |
| MEDIUM | Edits were not tied to the version the user saw. | Page edits, restore, and upload send `version_number`. A mismatch under the lock returns 409 `stale`, and the panel reloads. Tested. |
| MEDIUM | Split ignored rotations. | Split sends and applies rotations. |
| MEDIUM | Share links followed the current version. | Adding a version revokes active share links, and the UI says how many were revoked. Tested. |
| LOW | Duplicate flags are not recomputed after a version change. | Open: flags describe upload-time identity. Recorded for the duplicate-review slice. |
| LOW | Completed purge jobs kept version paths and hashes. | `version_files` is cleared on completion, like the other scrubbed fields. |
| LOW | Preview cache: shared temp name, `.part` left on failure, old-version previews kept. | Unique temp names, cleanup in `finally`, PNG signature check, and previews removed when a version is added. |
| LOW | Every thumbnail parsed the whole PDF. | A cached preview is served without parsing. A cache miss counts pages only and skips signature detection. |
| LOW | Signature detection could miss real signatures. | A `/ByteRange` with hex `/Contents` or a `/Sig` type counts, and pypdf AcroForm `/FT /Sig` fields are checked. |
| LOW | Restoring a missing version file returned 500 and read it into memory. | Returns 503 "stored version is unavailable" and streams the file. Tested. |
| LOW | Error status depended on message text. | `VersionError` carries `status` and `code`. |
| LOW | Accessibility and wording. | Split checkboxes name their page. Remove has a fixed label with `aria-pressed`. Move buttons no longer disable themselves, so focus is kept. Moves are announced. Touch targets are 44px. Rotated thumbnails are not clipped. The native file input is replaced by a styled label. |
| LOW | Merge had no review of order. | The merge panel lists the documents in merge order before confirming. Sources stay unchanged. |

## Verification

- `test_versions.py` and `test_purge.py`: 11 passed. Full local API suite: passing, with zbar-only tests skipped locally (they pass in the Linux image).
- The desktop and mobile journey `e2e/pages-versions.spec.ts` covers:
  - removing, rotating, and reordering pages;
  - saving as version 2 with the exact note;
  - downloading version 1 byte-identical;
  - the page count and OCR text after rebuild;
  - splitting into two new documents.

  The share-link journeys pass after the revocation change.

This scoped review is not the R4/9.5 release score.
