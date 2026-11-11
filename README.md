# Ripiano

Ripiano is a self-hosted document archive for a NAS. It combines quick mobile capture, automatic filing, full-text search, and a simple way to locate paper originals with stickers. The web app is an installable PWA for iOS and Android. An Android client shares the web interface and adds a native document scanner.

Ripiano is an independent implementation. Paperless-ngx v3.4.2 is the capability baseline, not a backend dependency or a workflow template. The product target is feature parity with that release plus a better day-to-day filing process.

## Screenshots

The first three pairs show the running development stack with three fictional PDF documents in a separate demo archive. Mobile captures use browser emulation of the PWA; the Android client adds a native multi-page scanner. The later screenshots show specific test journeys.

| Library on desktop | Library on mobile |
| --- | --- |
| ![Desktop Ripiano Library with three filed documents and paper locations](qa-artifacts/20261111-showcase/desktop/library-full.png) | ![Mobile Ripiano Library with three filed documents](qa-artifacts/20261111-showcase/mobile/library-full.png) |

The Appearance menu offers device setting, Light, Dark, and AMOLED black. The preference stays on the device; AMOLED uses a true black canvas and sidebar. These are browser captures of the same fictional archive.

| AMOLED on desktop | AMOLED on mobile |
| --- | --- |
| ![AMOLED Ripiano Library on desktop](qa-artifacts/20261111-appearance/amoled/desktop/library.png) | ![AMOLED Ripiano Library on mobile](qa-artifacts/20261111-appearance/amoled/mobile/library.png) |

| Dark on desktop | Dark on mobile |
| --- | --- |
| ![Dark Ripiano Library on desktop](qa-artifacts/20261111-appearance/dark/desktop/library.png) | ![Dark Ripiano Library on mobile](qa-artifacts/20261111-appearance/dark/mobile/library.png) |

| Add a document on desktop | Add a document on mobile |
| --- | --- |
| ![Desktop Add dialog with camera, photos, and files](qa-artifacts/20261111-showcase/desktop/add.png) | ![Mobile Add dialog with camera, photos, and files](qa-artifacts/20261111-showcase/mobile/add.png) |

| Paper binder on desktop | Paper binder on mobile |
| --- | --- |
| ![Desktop paper archive showing two documents in a binder](qa-artifacts/20261111-showcase/desktop/paper-contents.png) | ![Mobile paper archive showing two documents in a binder](qa-artifacts/20261111-showcase/mobile/paper-contents-full.png) |

| Exception-only Inbox on mobile |
| --- |
| ![Mobile Inbox showing a failed OCR document and retry action](qa-artifacts/5252d3e/inbox/mobile/failed-ocr.png) |

| Saved searches on desktop | Saved searches on mobile |
| --- | --- |
| ![Desktop Library with saved searches and filters](qa-artifacts/1896f45/saved-searches/desktop/saved-search.png) | ![Mobile Library with saved searches and filters](qa-artifacts/1896f45/saved-searches/mobile/saved-search.png) |

| Matching text on desktop | Matching text on mobile |
| --- | --- |
| ![Desktop search result showing a matching OCR passage](qa-artifacts/cb857fe/search-snippets/desktop/search-snippet.png) | ![Mobile search result showing a matching OCR passage](qa-artifacts/cb857fe/search-snippets/mobile/search-snippet.png) |

| Field search on desktop | Field search on mobile |
| --- | --- |
| ![Desktop Library with combined field search](qa-artifacts/93eb784/field-search/desktop/field-search.png) | ![Mobile Library with combined field search](qa-artifacts/93eb784/field-search/mobile/field-search.png) |

| Sorting the Library on desktop | Sorting the Library on mobile |
| --- | --- |
| ![Desktop Library sorted by title](qa-artifacts/e9bb89a/library-sort/desktop/library-sort.png) | ![Mobile Library sorted by title](qa-artifacts/e9bb89a/library-sort/mobile/library-sort.png) |

| Tag several documents on desktop | Tag several documents on mobile |
| --- | --- |
| ![Desktop Library after adding one tag to two selected documents](qa-artifacts/8200572/bulk-tags/desktop/bulk-tags.png) | ![Mobile Library after adding one tag to two selected documents](qa-artifacts/8200572/bulk-tags/mobile/bulk-tags.png) |

| Bulk sender and type filing on desktop | Bulk sender and type filing on mobile |
| --- | --- |
| ![Desktop Library after setting a sender and document type on two documents](qa-artifacts/20261111-bulk-filing/desktop/bulk-filing.png) | ![Mobile Library after setting a sender and document type on two documents](qa-artifacts/20261111-bulk-filing/mobile/bulk-filing.png) |

| Precise search on desktop | Precise search on mobile |
| --- | --- |
| ![Desktop Library matching a specific hyphenated document name and showing the manual tag first](qa-artifacts/20261111-search-precision/desktop/search-precision.png) | ![Mobile Library matching a specific hyphenated document name and showing the manual tag first](qa-artifacts/20261111-search-precision/mobile/search-precision.png) |

| Document notes on desktop | Document notes on mobile |
| --- | --- |
| ![Desktop document panel with a dated, searchable note](qa-artifacts/20261111-document-notes/desktop/document-notes.png) | ![Mobile document panel with a dated, searchable note](qa-artifacts/20261111-document-notes/mobile/document-notes.png) |

| Rebuild OCR on desktop | Rebuild OCR on mobile |
| --- | --- |
| ![Desktop document files section after rebuilding the searchable PDF](qa-artifacts/20261111-reprocess/desktop/reprocess.png) | ![Mobile document files section after rebuilding the searchable PDF](qa-artifacts/20261111-reprocess/mobile/reprocess.png) |

| Restore from Trash on desktop | Restore from Trash on mobile |
| --- | --- |
| ![Desktop Trash with a document and Restore action](qa-artifacts/20261111-trash/desktop/trash-page.png) | ![Mobile Trash with a document and Restore action](qa-artifacts/20261111-trash/mobile/trash-page.png) |

| Missing paper copy on desktop | Missing sticker lookup on mobile |
| --- | --- |
| ![Desktop paper-copy card marked missing with last known location and history](qa-artifacts/20261111-physical-missing/desktop/missing-paper-copy.png) | ![Mobile sticker lookup warning that a paper copy is missing](qa-artifacts/20261111-physical-missing/mobile/missing-sticker-lookup.png) |

| Shelf contents on desktop | Shelf contents on mobile |
| --- | --- |
| ![Desktop shelf-label lookup showing a paper copy in a nested box](qa-artifacts/20261111-location-label/desktop/shelf-contents.png) | ![Mobile shelf-label lookup showing a paper copy in a nested box](qa-artifacts/20261111-location-label/mobile/shelf-contents.png) |

| Related documents on desktop | Related documents on mobile |
| --- | --- |
| ![Desktop document panel linking a renewal to its policy](qa-artifacts/20261111-document-links/desktop/related-documents.png) | ![Mobile document panel linking a renewal to its policy](qa-artifacts/20261111-document-links/mobile/related-documents.png) |

| Custom details on desktop | Custom details on mobile |
| --- | --- |
| ![Desktop policy number saved as a custom detail](qa-artifacts/20261111-custom-fields/desktop/custom-field.png) | ![Mobile policy number saved as a custom detail](qa-artifacts/20261111-custom-fields/mobile/custom-field.png) |

| Custom detail filter on desktop | Custom detail filter on mobile |
| --- | --- |
| ![Desktop Library filtering by a policy number](qa-artifacts/20261111-custom-filter/desktop/custom-filter.png) | ![Mobile Library filtering by a policy number](qa-artifacts/20261111-custom-filter/mobile/custom-filter.png) |

| Number range filter on desktop | Number range filter on mobile |
| --- | --- |
| ![Desktop Library filtering a number field from 100 to 130](qa-artifacts/20261111-custom-range/desktop/custom-range.png) | ![Mobile Library filtering a number field from 100 to 130](qa-artifacts/20261111-custom-range/mobile/custom-range.png) |

| Portable export on desktop | Portable export on mobile |
| --- | --- |
| ![Desktop document files section with Export document ZIP action](qa-artifacts/20261111-document-export/desktop/export-action.png) | ![Mobile document files section with Export document ZIP action](qa-artifacts/20261111-document-export/mobile/export-action.png) |

## Planning documents

- [Product specification](docs/PRODUCT_SPEC.md): users, workflows, interaction design, and acceptance criteria.
- [Feature parity](docs/FEATURE_PARITY.md): Paperless capabilities and Ripiano delivery gates.
- [Architecture](docs/ARCHITECTURE.md): services, data model, classification, agents, security, deployment, and backup.
- [Backup and restore](docs/BACKUP_RESTORE.md): mounted volume layout, schedule, and clean-stack recovery.
- [Agent access](docs/AGENT_ACCESS.md): named MCP grants, permissions, and privacy boundaries.
- [Optional local Mac classifier](agents/local_classifier/README.md): Ollama through MCP, 10:00 LaunchAgent, and missed-run catch-up.
- [Implementation plan](docs/IMPLEMENTATION_PLAN.md): build order and verification gates.
- [Quality judges](docs/QUALITY_JUDGES.md): the 9.5 target, independent review rubric, and release blockers.
- [Design system](docs/DESIGN_SYSTEM.md): Ripiano colors, shared controls, focus behavior, and mobile density.
- [Portainer deployment](deploy/README.md): digest-pinned images, NAS volumes, HTTPS, and backup mount.

## First implementation slice

The current slice has owner setup and sign-in, PDF/JPEG/PNG upload, preserved originals, background OCR to PDF/A, text search, a responsive installable PWA, scheduled or manual checksum-verified backups, tags, correspondents, document types, local phrase-based automatic filing, exact duplicate flags, a physical archive, and named MCP agent grants. Camera, gallery, and file selection are available through the browser. A native Android debug build adds multi-page capture and keeps pending scans on-device for retry; it has not passed real-device validation. Paper copies can receive a stable sticker and QR label, be placed in nested locations, and be found again from a sticker link. An agent can be given separate search, OCR-text, and tag-changing permissions, with optional tag filtering, expiry, revocation, and an activity log. An optional Mac worker can ask a local Ollama model to apply existing tags through that grant. Failed OCR can be retried; ready documents can rebuild the searchable PDF from the preserved original. This is the beginning of the staged implementation, not the complete Paperless feature set. Calibrated pretrained classification, automatic OAuth agent sign-in, and the rest of the [parity matrix](docs/FEATURE_PARITY.md) are still to be built.

### Run locally

Documents can optionally be marked **Needs action** with a due date and note. The separate action list shows only open follow-ups; completing one keeps the document in the archive. Uploading and automatic tags do not require this step.

The **Inbox** shows exceptions only: failed OCR and exact copies that have not been reviewed. Retry OCR or acknowledge that both copies should stay. Ordinary uploads go straight to the Library.

In **Senders** and **Document types**, add a matching phrase to a name to file new and existing documents by title or OCR text. A longer matching phrase wins when more than one name matches; the same phrase cannot target two names of the same kind. The document details show when a value came from a phrase; changing or clearing it there keeps that manual decision on later reprocessing. Automatic tags also stay automatic when you edit an unrelated detail. Tag, sender, and type phrase edits recheck only documents they may affect, so new OCR work is not held behind a full archive pass.

Tags can be grouped under other tags. Create a nested tag from the **Under** picker or move an existing tag from its card. Filtering the Library by a parent finds documents tagged with any nested child, including deeper levels; documents tagged with both parent and child appear once. Agent grants that use a tag filter continue to require the exact granted tag.

For a batch of files, Ripiano continues after an unsupported file and names each rejected file in the result. Accepted files appear in the Library without another filing step.

With a hardware keyboard, press **/** to focus Library search from any archive screen, or **N** to open Add. These shortcuts stay inactive while typing or using a dialog.

1. Copy `.env.example` to `.env` and replace the three example secrets with strong unique values.
2. Run `docker compose up --build -d` from this directory.
3. Open `http://localhost:8080`. Enter the `RIPIANO_SETUP_KEY` from `.env` to create the owner account.

For a NAS deployment, use the [complete Portainer Compose example](deploy/compose.portainer.yaml) and the [example environment values](deploy/portainer.env.example). The example maps the database, media, and backup folders to persistent Synology paths and publishes only the web port; the API, OCR worker, maintenance worker, scheduler, broker, and MCP stay inside the stack. OCR work has its own queue so a long rule recheck or backup does not hold new uploads. Portainer should receive the complete Compose file and the environment variables, with real secrets and released image digests. A short excerpt shows the important mounts:

```yaml
services:
  db:
    volumes:
      - ${RIPIANO_DB_PATH}:/var/lib/postgresql/data
  api:
    volumes:
      - ${RIPIANO_MEDIA_PATH}:/data
      - ${RIPIANO_BACKUP_PATH}:/backup:ro
  worker:
    volumes:
      - ${RIPIANO_MEDIA_PATH}:/data
  maintenance_worker:
    volumes:
      - ${RIPIANO_MEDIA_PATH}:/data:ro
      - ${RIPIANO_BACKUP_PATH}:/backup
  web:
    ports:
      - "${RIPIANO_PORT:-8080}:8080"
```

This excerpt illustrates storage and exposure; use the linked full stack for deployment. Set an HTTPS `RIPIANO_PUBLIC_ORIGIN`, the reverse proxy hostname in `RIPIANO_ALLOWED_HOSTS`, and give container UID 10001 write access to the media and backup folders. Point Synology's HTTPS reverse proxy at the web port and Hyper Backup at the backup folder's `complete/` subfolder. [Deployment details](deploy/README.md) include image pinning and NAS permissions; [backup/restore instructions](docs/BACKUP_RESTORE.md) cover recovery. Backblaze B2 configuration stays in Synology. A local clean-stack restore passed with documents, locations, duplicate links, and revoked agent grants, but NAS-specific permissions and restore still need verification before storing real documents. No release images have been published from this draft PR yet.

### Work on the services

- API: `cd services/api && uv sync && RIPIANO_DEBUG=1 uv run pytest -q`
- Web: `cd apps/web && npm ci && npm run build`
- Android debug build: `cd apps/android && ./gradlew :app:assembleDebug` with JDK 17 and Android SDK 36. See [Android setup](apps/android/README.md).
- Browser journey (running local stack and a disposable owner account): `cd apps/web && RIPIANO_E2E_ORIGIN=http://localhost:8080 RIPIANO_E2E_USERNAME=... RIPIANO_E2E_PASSWORD=... npm run test:e2e`. This creates test documents, tags, and locations in that account.

The document originals are stored under the mounted media path. OCR output is derived and can be rebuilt. Simple search finds titles, OCR text, tag names, correspondent names, document types, action notes, and sticker codes. Full-text terms must match the query together; a partial rank alone does not pull an unrelated document into results. Search results show the matching passage from OCR text or action notes, or the matching sticker code; the unfiltered Library stays compact. To narrow search by field, use `title:`, `text:`, `note:`, `tag:`, `sender:`, `type:`, `sticker:`, or `date:YYYY-MM-DD`; quote values containing spaces, such as `sender:"City office"`. Multiple field terms and ordinary text combine. The Library can also narrow results with the visual tag, sender, type, and date filters. Save a search to reopen it in one tap; rename it, update its criteria, or delete it from the Library. Sort the Library by relevance, date added, document date, or title; date-less documents stay at the end of document-date sorts. Select up to 100 loaded documents to add or remove a tag, set or clear the sender, or set or clear the document type together; those changes count as manual corrections for future automatic filing. The Library and Needs action lists load additional results in cursor-based pages of 50; Refresh shows new arrivals. Boolean and range query syntax remain future work.

The document panel keeps dated notes separate from follow-ups. Notes can be added or deleted, found through Library search (including `note:`), and retrieved in older pages when the history grows.

Under **Custom details**, create a text, number, date, or yes/no field once and set it on any document. Only fields with values appear by default; choose an unused field when you need it. A field value is found by ordinary Library search, by a visual field and value filter, or with `field:"Policy number=PN-123"`. Number and date filters accept an exact value or inclusive from/to bounds. Save any visual filter as a search to reuse it. You can rename a field across documents and delete an unused field after removing its values and saved searches. Custom values are included in the portable document ZIP.

The same panel can link related documents. Search for the other document by title or text, then choose **Link**. The connection appears on both documents, so either side opens the other. Moving one document to Trash hides the link until it is restored; its underlying relationship is retained.

Use **Export document ZIP** under Files to download the preserved original, the searchable PDF and OCR text when available, and a readable `manifest.json` with tags, notes, related documents, and paper-copy history. Each file has a SHA-256 checksum in the manifest. This is a single-document portable export; a complete archive export/import tool is still planned.

Move a completed document to **Trash** from its detail panel and restore it later with its original, notes, tags, and sticker history intact. Trashed documents disappear from Library search, Needs action, downloads, and agent tools. A sticker scan explains that its document is in Trash. Processing must finish before a document can be moved. Trash does not erase files automatically; permanent deletion and retention controls are still future work.

If a paper copy is missing, mark its sticker **Missing** from the document panel. Ripiano keeps the last known location, shows a warning when the sticker is scanned, and records the report in its history. Mark it **Found** before assigning a new location; the sticker identity stays the same.

Each shelf or box also has a stable `L-` code and a printable QR label. Scan it to see the paper copies stored there, including copies in nested locations, or type the code in **Your paper archive**. Large locations load their contents in pages of 50. Missing copies remain listed at their last known location with a warning.

### Optional Telegram input

Create a bot with BotFather. Set `RIPIANO_TELEGRAM_BOT_TOKEN` and `RIPIANO_TELEGRAM_OWNER_USERNAME` in `.env`, then run `docker compose --profile telegram up -d`. Send `/start` to the bot in a private chat; it returns your numeric chat ID. Put that ID in `RIPIANO_TELEGRAM_ALLOWED_CHAT_IDS` and restart the Telegram service. You can now send or forward PDF, JPEG, PNG, or photos to the bot. Each accepted file enters the same OCR and search pipeline as web uploads. For multiple people, list IDs separated by commas; all currently file into the configured owner archive. Only private chats are accepted, and the bot exposes no inbound NAS port.

Telegram's [Bot API limits standard bot downloads to 20 MB](https://core.telegram.org/bots/api#getfile). Telegram handles the file before Ripiano downloads it, so use the direct app upload when the document must never pass through Telegram. Updates remain on Telegram for at most 24 hours; prolonged NAS downtime can miss messages. The bot token must remain secret.

### Optional watched folder

Mount a NAS folder at `RIPIANO_WATCH_PATH`, set `RIPIANO_WATCH_OWNER_USERNAME` to an existing account, and start `docker compose --profile watch up -d`. The mount is read-only to Ripiano. Stable PDF, PNG, and JPEG files are copied into the archive and left in the incoming folder. The same path and bytes import once across restarts; changing a file creates a new document. Files above the configured 25 MB limit are skipped. Set `RIPIANO_WATCH_POLL_SECONDS` to adjust the default five-second poll.

The planning documents remain the implementation baseline. No Paperless source code is included in this repository.
