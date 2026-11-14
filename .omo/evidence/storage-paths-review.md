# Storage paths review

A quick independent read-only review returned **APPROVE**, with 1 medium and 3 low findings. It confirmed the following:
- **No path traversal:** every value and template part becomes one sanitised component. `..` becomes "None", and leading dots are stripped.
- **Manifest compatibility:** `_safe_path` still sees the `documents/` prefix.
- **Owner isolation** on create, list, delete, and document PATCH.
- **Correct deletes:** SET_NULL and CASCADE behave as intended.
- **Exports and backups:** `portable.py` and the backups include the new model.

| Severity | Finding | Resolution |
| --- | --- | --- |
| MEDIUM | Names were cut by characters, not bytes; emoji or CJK names could exceed 255-byte filesystem limits on Linux NAS volumes. | `fit_bytes` caps every component at 180 UTF-8 bytes, in storage-path rendering and in the browse-copy leaf names. Tested with 80 emoji. |
| LOW | A rendered folder could imitate another document's `--<id>` leaf. | `--` inside rendered folder names becomes `-`. Tested. |
| LOW | A trailing slash counted toward the depth limit. | Depth is counted after stripping slashes. Tested. |
| LOW | The count read "1 documents" and included trashed documents; there is no remove confirmation. | Pluralised, and only non-trashed documents are counted. Removing a path only returns its documents to the year layout, so no confirmation was added. |

Verification: `test_storage_paths.py` and `test_browse_export.py` give 9 passed. The desktop and mobile `e2e/storage-paths.spec.ts` covers creating a path, assigning it to a document, saving, and removing the path, which clears the document's path.
