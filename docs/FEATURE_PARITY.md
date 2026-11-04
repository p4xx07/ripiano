# Paperless-ngx feature parity contract

Baseline: Paperless-ngx **v3.4.2**, released 2026-11-03. Ripiano is independent; this table defines behavior to preserve, not code to copy. Product improvements are defined in [PRODUCT_SPEC.md](PRODUCT_SPEC.md). The implementation must expand each row into API and end-to-end scenarios before marking it complete. A later Paperless release does not silently expand this pinned baseline.

Milestones: **R1** = safe daily archive; **R2** = full daily workflow and physical filing; **R3** = advanced management and integrations; **R4** = verified parity. R4 requires every row below, including optional features when explicitly enabled. Earlier releases may be useful without claiming full parity.

| Capability to preserve | Ripiano behavior / improvement | Target gate |
| --- | --- | --- |
| Web upload, drag-and-drop, consume folder, scanner imports, API upload | All channels reach the same durable ingestion pipeline; PWA and Android capture add simpler mobile paths | R1-R2 |
| Incoming email accounts and filtering rules, including OAuth-capable providers | Import attachments with source metadata; email configuration lives in Integrations | R3 |
| PDF, image, Office, and email file processing through optional converters | Preserve originals; produce searchable previews/archive versions where supported; show unsupported-format errors | R1-R3 |
| OCR, selectable text, PDF/A, language settings, reprocessing | Local default; retry/reprocess without losing originals; compare OCR engines on actual scans | R1-R3 |
| Barcode/QR extraction, ASN detection, tag barcodes, split pages | Support documented paper scan workflows; physical-copy stickers add a separate stable identity | R2-R3 |
| Tags, nested tags, correspondents, document types, storage paths, dates | Keep all metadata fields; replace manual filing with suggestions and exception review | R1-R2 |
| Typed custom fields and document links | Create/edit/filter/search fields and links with permissions | R3 |
| Exact, fuzzy, rule-based, and learned matching; suggestions | Rules plus local pretrained model and correction examples; explain why suggestions appear | R2-R3 |
| Optional AI suggestions, similarity search, document chat | Opt-in provider selection, including local endpoints; show when content would leave the NAS | R3-R4 |
| Full-text search, field syntax, snippets, filters, sort, saved views | Search-first Library with simple filters and a power-user query mode; saved collections | R1-R4 |
| Duplicate detection and duplicate review | Exact/likely duplicate view; never silently throw away a captured original | R2-R3 |
| Preview, original/archive download, notes, document history | Show common actions first; retain underlying versions and audit events | R1-R3 |
| File versions and merge-as-versions | Root metadata with version-specific file/text; explicit selection and history | R3 |
| PDF rotate, split, merge, reorder, delete pages | Warn when an edit changes an original or invalidates a digital signature | R3 |
| Bulk edits, retagging, reprocessing, trash/restore | Preview and undo where possible; background job status for long actions | R2-R3 |
| Workflows: consume/add/update/scheduled triggers, filters, assignment/removal, email, webhook, password removal, AI actions | Guided recipes plus full advanced editor; deterministic execution and visible run history | R3-R4 |
| Users, groups, object permissions, ownership, 2FA, OIDC/remote auth where applicable | Same access behavior across PWA, Android, REST, and MCP; agent grants are additional restrictions | R1-R4 |
| Share links, expiring links, bundles, email sending | Off by default, clear preview of recipient reach, expiry and revocation | R3 |
| REST API, API tokens, documented schema, task/status endpoints | Versioned API and OpenAPI, with permission parity and compatibility tests | R1-R4 |
| Dashboard, statistics, saved views, system monitoring and task controls | Home shows useful work without setup; advanced monitoring stays available | R2-R4 |
| Export/import, maintenance, index rebuild, backup/restore | Open manifest and originals; scheduled verified snapshots to mounted volume | R1-R4 |
| Search, metadata, and interface localization | Italian and English at minimum; no hard-coded text in components | R2-R4 |
| Keyboard shortcuts and accessible desktop interaction | Common actions and search are keyboard operable; mobile has touch-sized controls | R2-R4 |

## Additional Ripiano capabilities

These are not substitutes for parity rows: physical-copy hierarchy, printable document/container stickers, movement history, exception-only Inbox, first-class Needs action/reminders, installable iOS/Android PWA, Android native scanner, named per-agent MCP grants, optional daily local-PC worker, and scheduled backups visible in the app.

## Evidence required at R4

- Freeze and archive the upstream v3.4.2 documentation/API schema used for comparison; identify any capability missing from this initial table and add a row.
- For each row: automated API test where feasible and a real UI scenario for user-facing behavior. Record intentional behavioral changes with rationale.
- Cross-client parity check: a feature exposed in PWA must be available in the Android client, except that Android may add native capture behavior. Admin tools may use a responsive web view inside the client.
- Permission matrix tests for human users and at least two agents with different scopes and document filters.
- Representative Italian/English files, mixed document formats, duplicate scans, barcode sheets, signed PDFs, email attachments, and restore snapshots.
- No release is labelled Paperless feature-complete until every row is verified, not merely implemented in a hidden API.

## Sources

- [Paperless-ngx release v3.4.2](https://github.com/paperless-ngx/paperless-ngx/releases/tag/v3.4.2)
- [Usage and feature documentation](https://docs.paperless-ngx.com/usage/)
- [Advanced matching and AI](https://docs.paperless-ngx.com/advanced_usage/)
- [REST API](https://docs.paperless-ngx.com/api/)
- [Administration and exporter](https://docs.paperless-ngx.com/administration/)
