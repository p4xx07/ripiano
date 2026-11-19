# Correspondents and document types: incremental evidence

Base commit: `44c3594`. This slice adds owner-scoped correspondents and document types, creation/rename/deletion in Tags & filing, optional selection or inline creation in the document editor, and search by either name. Deletion protects values still assigned to documents.

Verification: `RIPIANO_DEBUG=1 uv run pytest -q` passed 27 tests. Django system and migration checks passed. `npm run build` passed. Local Compose rebuilt, applied additive migration `0012`, and served the API/PWA. All 22 desktop/mobile browser journeys passed. The new journey creates and renames a sender, creates a document type, assigns both, searches by each, creates a second sender directly in the document editor, and finds the document again. It waits for the debounced search response and asserts exactly one matching document. The API test also checks case-insensitive uniqueness, owner isolation, protected deletion, and clearing metadata.

Rendered [desktop vocabulary](filing/desktop/vocabularies.png), [mobile vocabulary](filing/mobile/vocabularies.png), [mobile editor](filing/mobile/editor.png), and [mobile search](filing/mobile/search.png) captures were inspected. The mobile cards stack and the document form remains operable without horizontal clipping. The screenshots use a synthetic local QA account.

This is metadata management, not automatic correspondent/type classification. Installed PWA, Android scanner hardware, and NAS restore remain separate release gates.
