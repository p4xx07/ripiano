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

| Review a custom-field type change on desktop | Review a custom-field type change on mobile |
| --- | --- |
| ![Desktop dialog explaining why an invalid value blocks a type change](qa-artifacts/20261112-custom-type/desktop/blocked.png) | ![Mobile dialog explaining why an invalid value blocks a type change](qa-artifacts/20261112-custom-type/mobile/blocked.png) |

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

| Batch Restore on desktop | Batch Restore on mobile |
| --- | --- |
| ![Desktop Trash with two selected documents and batch Restore](qa-artifacts/20261112-bulk-trash/desktop/selected.png) | ![Mobile Trash with two selected documents and batch Restore](qa-artifacts/20261112-bulk-trash/mobile/selected.png) |

| Review automatic Trash cleanup on desktop | Review automatic Trash cleanup on mobile |
| --- | --- |
| ![Desktop confirmation showing the 30-day Trash threshold and eligible count](qa-artifacts/20261112-trash-retention/desktop/confirmation.png) | ![Mobile confirmation showing the 30-day Trash threshold and eligible count](qa-artifacts/20261112-trash-retention/mobile/confirmation.png) |

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

| Word upload found by text on desktop | Word upload found by text on mobile |
| --- | --- |
| ![Desktop Library finding text from a Word document](qa-artifacts/20261112-office-upload/desktop/search.png) | ![Mobile Library finding text from a Word document](qa-artifacts/20261112-office-upload/mobile/search.png) |

| NAS browse copy on desktop | NAS browse copy on mobile |
| --- | --- |
| ![Desktop Backups section showing a readable NAS copy](qa-artifacts/20261112-nas-browse/desktop/backups.png) | ![Mobile Backups section showing a readable NAS copy](qa-artifacts/20261112-nas-browse/mobile/backups.png) |

| Collection export on desktop | Collection export on mobile |
| --- | --- |
| ![Desktop Library with two selected documents and a collection ZIP download](qa-artifacts/20261112-collection-export/desktop/selected.png) | ![Mobile Library with two selected documents and a collection ZIP download](qa-artifacts/20261112-collection-export/mobile/selected.png) |

| Expiring share link on desktop | Expiring share link on mobile |
| --- | --- |
| ![Desktop document panel showing a one-time original-file link and expiry controls, with the token masked](qa-artifacts/20261112-share-links/desktop/created.png) | ![Mobile document panel showing a one-time original-file link and expiry controls, with the token masked](qa-artifacts/20261112-share-links/mobile/created.png) |

| Opt-in automatic filing on desktop | Opt-in automatic filing on mobile |
| --- | --- |
| ![Desktop learned filing panel with the optional automatic filing switch enabled](qa-artifacts/20261114-auto-filing/desktop/auto-filing.png) | ![Mobile learned filing panel showing the optional switch and per-field readiness](qa-artifacts/20261114-auto-filing/mobile/auto-filing.png) |

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

The current slice has owner setup and sign-in, PDF/JPEG/PNG, email (.eml), and Office/OpenDocument/RTF upload, IMAP email intake, preserved originals, background OCR to PDF/A for PDF/images and searchable PDF conversion for Office files, text search, a responsive installable PWA, scheduled or manual checksum-verified backups, tags, correspondents, document types, local phrase-based automatic filing, exact duplicate flags, a physical archive, and named MCP agent grants. Camera, gallery, and file selection are available through the browser. A native Android debug build adds multi-page capture and keeps pending scans on-device for retry; it has not passed real-device validation. Paper copies can receive a stable sticker and QR label, be placed in nested locations, and be found again from a sticker link. An agent can be given separate search, OCR-text, tag-changing, and sender/type-filing permissions, with optional tag filtering, expiry, revocation, and an activity log. An optional Mac worker can ask a local Ollama model to apply existing tags through that grant. Failed OCR can be retried; ready documents can rebuild the searchable PDF from the preserved original. In Library selection mode, use **OCR actions** to retry failed documents or rebuild searchable PDFs for up to 100 selected documents; files already processing are skipped, and originals remain unchanged. Locally trained filing suggestions can also be applied automatically to new documents when the owner opts in and strict confidence checks pass. This is the beginning of the staged implementation, not the complete Paperless feature set. Optional AI-provider suggestions, automatic OAuth agent sign-in, and the remaining [parity matrix](docs/FEATURE_PARITY.md) work are still open.

### Interface language (in progress)

English is the default interface language on every device. The sign-in screen and sidebar let you opt into the partial Italian preview or follow the device language instead. The choice is saved in this browser and also controls date formatting and the language requested from the API. The app shell, daily Library search/filter/upload flow, Backups, and several filing and archive panels have Italian text. Advanced Library bulk actions, document detail, other screens, and many API errors still use English. Further localization is deferred; the [parity matrix](docs/FEATURE_PARITY.md) tracks it separately from the English experience.

### Run locally

Documents can optionally be marked **Needs action** with a due date and note. The separate action list shows only open follow-ups; completing one keeps the document in the archive. Uploading and automatic tags do not require this step.

The **Inbox** shows exceptions only: failed OCR and exact copies that have not been reviewed. Retry OCR or acknowledge that both copies should stay. Ordinary uploads go straight to the Library.

In **Senders** and **Document types**, add a matching phrase to a name to file new and existing documents by title or OCR text. A longer matching phrase wins when more than one name matches; the same phrase cannot target two names of the same kind. The document details show when a value came from a phrase; changing or clearing it there keeps that manual decision on later reprocessing. Automatic tags also stay automatic when you edit an unrelated detail. Tag, sender, and type phrase edits recheck only documents they may affect, so new OCR work is not held behind a full archive pass.

Tags can be grouped under other tags. Create a nested tag from the **Under** picker or move an existing tag from its card. Filtering the Library by a parent finds documents tagged with any nested child, including deeper levels; documents tagged with both parent and child appear once. Agent grants that use a tag filter continue to require the exact granted tag.

For a batch of files, Ripiano continues after an unsupported file and names each rejected file in the result. Accepted files appear in the Library without another filing step.

Word `.docx`, Excel `.xlsx`, and PowerPoint `.pptx` files use the private Gotenberg LibreOffice service in the Compose stack. The original bytes are preserved; a searchable PDF is generated for viewing and search. Older binary `.doc`, `.xls`, and `.ppt` files, OpenDocument `.odt`, `.ods`, and `.odp`, and `.rtf` use the same path; files are checked by content, and OpenDocument or OOXML files with macros are refused. Emails (`.eml`) keep the original message and become a searchable PDF of the sender, recipients, date, subject, text, and attachment names. The page is built from escaped text, so remote images, links, scripts, and styles in the message are never loaded. Outlook `.msg` files are read locally (subject, sender, recipients, date, text, and attachment names) and rendered the same way. Office-derived PDFs currently use normal PDF output because PDF/A conversion damaged extracted text in a real local test. The converter has no published port and does not contact a cloud provider.

With a hardware keyboard, press **/** to focus Library search from any archive screen, or **N** to open Add. These shortcuts stay inactive while typing or using a dialog.

1. Copy `.env.example` to `.env` and replace the three example secrets with strong unique values.
2. Run `docker compose up --build -d` from this directory.
3. Open `http://localhost:8080`. Enter the `RIPIANO_SETUP_KEY` from `.env` to create the owner account.

In **Backups**, **Build browse copy** writes a human-readable, owner-scoped year/tag tree to the mounted NAS backup volume under `browse/owners/.../complete`. It includes the preserved original, available searchable PDF, OCR text, and metadata for each active document. This is an on-demand copy for NAS browsing; the checksum-verified restore snapshots remain separately under `complete`. Rebuild after changing titles or tags. The owner can cancel a backup or browse copy while it is queued, and retry a failed or cancelled run; a retry is recorded as a new run. An active run cannot be interrupted because a partial output could be misleading.

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

The document originals are stored under the mounted media path. OCR output is derived and can be rebuilt. Simple search finds titles, OCR text, tag names, correspondent names, document types, action notes, and sticker codes. Full-text terms must match the query together; a partial rank alone does not pull an unrelated document into results. Search results show the matching passage from OCR text or action notes, or the matching sticker code; the unfiltered Library stays compact. To narrow search by field, use `title:`, `text:`, `note:`, `tag:`, `sender:`, `type:`, `sticker:`, or `date:YYYY-MM-DD`; quote values containing spaces, such as `sender:"City office"`. Multiple field terms and ordinary text combine. The Library can also narrow results with the visual tag, sender, type, and date filters. Save a search to reopen it in one tap; rename it, update its criteria, or delete it from the Library. Sort the Library by relevance, date added, document date, or title; date-less documents stay at the end of document-date sorts. Select up to 100 loaded documents to add or remove a tag, set or clear the sender, or set or clear the document type, set or clear a shared document date, retry failed OCR, rebuild searchable PDFs, or move a batch to Trash; filing changes count as manual corrections for future automatic filing. The Library and Needs action lists load additional results in cursor-based pages of 50; Refresh shows new arrivals. Boolean and range query syntax remain future work.

The document panel keeps dated notes separate from follow-ups. Notes can be added or deleted, found through Library search (including `note:`), and retrieved in older pages when the history grows.

Under **Custom details**, create a text, number, date, or yes/no field once and set it on any document. Only fields with values appear by default; choose an unused field when you need it. A field value is found by ordinary Library search, by a visual field and value filter, or with `field:"Policy number=PN-123"`. Number and date filters accept an exact value or inclusive from/to bounds. Save any visual filter as a search to reuse it. You can rename a field across documents. To change its type, review how every existing value would convert; invalid values and saved searches using the field block the change until you fix them. A successful change converts all values in one database transaction. Delete an unused field after removing its values and saved searches. Custom values are included in the portable document ZIP.

The same panel can link related documents. Search for the other document by title or text, then choose **Link**. The connection appears on both documents, so either side opens the other. Moving one document to Trash hides the link until it is restored; its underlying relationship is retained.

Use **Export document ZIP** under Files to download the preserved original, the searchable PDF and OCR text when available, and a readable `manifest.json` with tags, notes, related documents, and paper-copy history. Each file has a SHA-256 checksum in the manifest. In the Library, select up to 20 documents and open **Export selected** to download one collection ZIP. Its root manifest identifies each document and gives checksums for files in stable ID-based folders. A complete archive export/import tool is still planned.

To give someone a document without an account, open **Share original** in its document panel, choose a 1, 7, or 30-day expiry, and create a link. Copy it while it is shown: Ripiano stores only a hash of the token and cannot display that URL later. Anyone with the URL can download the original without signing in. You can revoke an active link at any time; moving a document to Trash revokes its links permanently, even if the document is restored. A link only exposes original file bytes, not notes, tags, OCR text, or the rest of the archive. On a NAS, the recipient must be able to reach the HTTPS `RIPIANO_PUBLIC_ORIGIN`; a Tailscale-only address only works for people on that tailnet.

Move a completed document to **Trash** from its detail panel and restore it later with its original, notes, tags, and sticker history intact. Trashed documents disappear from Library search, Needs action, downloads, and agent tools. A sticker scan explains that its document is in Trash. Processing must finish before a document can be moved. Select documents in the Library to move a batch to Trash after confirmation, and select documents in Trash to restore them together. These actions reject the whole batch if any document is inaccessible or in the wrong state. A confirmed **Delete permanently** action removes the record and paper-copy sticker history, then the maintenance worker removes its live original and archive files after any active backup finishes. Trash shows cleanup status and lets you retry a failed cleanup. Previously completed snapshots may still contain the document until their configured retention expires. Automatic cleanup is off by default. In Trash, choose 30–3650 days and review the current eligible count before enabling a daily 03:00 Europe/Rome cleanup. Disabling it stops future automatic deletions; cleanup already requested still completes.

If a paper copy is missing, mark its sticker **Missing** from the document panel. Ripiano keeps the last known location, shows a warning when the sticker is scanned, and records the report in its history. Mark it **Found** before assigning a new location; the sticker identity stays the same.

Each shelf or box also has a stable `L-` code and a printable QR label. Scan it to see the paper copies stored there, including copies in nested locations, or type the code in **Your paper archive**. Large locations load their contents in pages of 50. Missing copies remain listed at their last known location with a warning.

### Optional Telegram input

Create a bot with BotFather. Set `RIPIANO_TELEGRAM_BOT_TOKEN` and `RIPIANO_TELEGRAM_OWNER_USERNAME` in `.env`, then run `docker compose --profile telegram up -d`. Send `/start` to the bot in a private chat; it returns your numeric chat ID. Put that ID in `RIPIANO_TELEGRAM_ALLOWED_CHAT_IDS` and restart the Telegram service. You can now send or forward PDF, JPEG, PNG, or photos to the bot. Each accepted file enters the same OCR and search pipeline as web uploads. For multiple people, list IDs separated by commas; all currently file into the configured owner archive. Only private chats are accepted, and the bot exposes no inbound NAS port.

Telegram's [Bot API limits standard bot downloads to 20 MB](https://core.telegram.org/bots/api#getfile). Telegram handles the file before Ripiano downloads it, so use the direct app upload when the document must never pass through Telegram. Updates remain on Telegram for at most 24 hours; prolonged NAS downtime can miss messages. The bot token must remain secret.

### Storage paths

Under **Tags & filing → Storage paths**, define folder layouts such as `{correspondent}/{year}/{month}`. Choose one on a document, and the next NAS browse copy places it there instead of under its year.
- **Placeholders:** `{year}`, `{month}`, `{day}`, `{added_year}`, `{added_month}`, `{correspondent}`, `{document_type}`, `{title}`, `{asn}`, `{tag}`, and `{source}`.
- **Safe names:** values are made into safe single folder names. Slashes and reserved names such as `CON` are replaced.
- **Originals:** Ripiano's managed originals never move.

### Matching rules

Tag, sender, and document-type rules are under **Tags & filing**. Each rule can match in one of five ways:
- the **exact phrase**;
- **any** of its words (whole words only);
- **all** of its words;
- a **similar spelling**, which tolerates OCR mistakes;
- a **regular expression**, for example `fattura n\. \d+`.

Some limits apply:
- **Regular expressions** use full Unicode case folding, so `Straße` also matches "STRASSE". Each search stops after 0.25 s, and only the first 100,000 characters are searched.
- **Similar spelling** compares up to 6 words against the first 20,000 words of a document, at 85% similarity. One wrong letter in a word of six letters or fewer is not tolerated.
- **Every mode:** rules are evaluated before any database lock is taken.

Existing documents are rechecked in the background when you add a rule.

### Overview

**Overview** shows:
- totals and storage used;
- what needs a look (unreadable documents, overdue follow-ups, exact copies, mailbox problems, failed workflow runs), each linking to the right screen;
- documents added per month over the last year;
- the most common types, tags, and sources;
- the last backup (for the archive owner).

### API tokens

Under **Security → API tokens**, create a personal token for your scripts. It is shown once, and you choose an expiry of 7–365 days. Send it as `Authorization: Token rip_…` on `/api/` requests.
- **Access:** the token acts with your access, needs no CSRF token, and cannot use sign-in or account-security endpoints.
- **Revoking:** revoke a token at any time. Last use is shown next to each token.
- **Reference:** `/api/schema.json` is an OpenAPI 3.1 outline of every route.
- **Agents:** MCP agents keep their own, more limited grants (see Agents).

### Share and email

- **Single document:** a document's **Share original** creates an expiring, revocable link to its original.
- **Several documents:** in Library selection mode, **Share as one link** gives the selected originals (up to 50 documents, 200 MB) as one ZIP download. The link lasts 1–30 days and can be revoked, and each original is checksum-verified while the ZIP is built.
- **New versions:** adding a new version of a document revokes the links and bundles that include it.
- **Email:** **Email this document** sends the original (checksum-verified) or the searchable PDF through the server's SMTP settings. It is off unless the operator sets `RIPIANO_DOCUMENT_EMAIL=1`; SMTP alone (for workflows) does not enable it. Each account can email up to 30 recipients per hour, replies go to the account's email address, and the send history is shown on the document.
- **Bundle ZIPs:** each bundle's ZIP is built once in the background and deleted when the link ends. Moving a bundled document to Trash or adding a new version revokes the bundle, and restoring the document does not re-share it.

### Move to a new server

`docker compose exec maintenance_worker .venv/bin/python manage.py export_archive /backup/export-2026-11` writes a portable folder:
- `manifest.json` lists every account, document, tag, note, paper copy, workflow, and setting, with stable IDs.
- `media/` holds every original, older version, and searchable PDF, each listed with its SHA-256.

On the new server, start an empty stack, copy the folder to a mounted path, and run `manage.py import_archive /path/to/export --yes`. The import refuses a non-empty instance, and it refuses any file whose checksum differs from the export.
- **Passwords:** account passwords carry over.
- **Encrypted secrets:** mailbox and two-step secrets decrypt only with the same `RIPIANO_MAIL_KEY` or `RIPIANO_SECRET_KEY`.
- **Not exported:** backup history, cleanup jobs, and input cursors.

Scheduled snapshots (see Backups) remain the disaster-recovery path. This export is for moving or upgrading.

### Two-step sign-in

Open **Security**, confirm your password, and scan the QR code with any authenticator app. After that, Ripiano asks for a 6-digit code after your password.
- **Recovery codes:** you get 10 single-use codes for a lost phone. They are shown once and stored hashed.
- **Lockout:** after 5 wrong codes, code entry locks for 15 minutes.
- **Storage:** the authenticator secret is encrypted with the same key as mailbox passwords (`RIPIANO_MAIL_KEY`, or one derived from `RIPIANO_SECRET_KEY`). When rotating it, keep the old key listed after the new one in `RIPIANO_MAIL_KEY`.
- **Agents:** agent tokens are separate and unaffected.
- **Admin:** Django admin (`/admin/`) has no separate password form. Sign in to Ripiano first, then open it.
- **Throttling:** failed sign-ins are limited per username and per client address.
- **Lost phone, no recovery codes:** run `manage.py reset_two_factor <username>`.

### People and sharing

The first account is the admin. Under **People**, the admin adds people (each gets a private archive), resets passwords, turns accounts off, and creates groups such as "Family".
- **Share a document:** open it, then **People with access → Manage access**. Choose a person or a group and either *Can view* or *Can edit details*.
- **What they get:** the document appears under their **Shared with me**. Viewers can read it, download it, and read its notes. Editors can also change the title, date, and follow-up, and add notes.
- **What stays with you:** filing, tags, files, pages, versions, share links, paper copies, and Trash.
- **Ending access:** removing a grant, removing someone from the group, turning the account off, or moving the document to Trash all end access immediately.
- **Passwords:** a password reset ends that person's other sessions and API tokens. API tokens cannot manage people or groups.

### Learned suggestions

Ripiano learns from the senders, document types, and tags you set by hand, on your own server. It learns again every night, or when you press **Tags & filing → Learned suggestions → Learn now**.
- **When it suggests:** only when it is at least 60% likely to be right. The probability is calibrated on documents the model had not seen.
- **Automatic filing is optional:** in **Tags & filing → Learned suggestions**, turn on **File new documents automatically when very confident**. It applies only after OCR on new documents. Each assignment needs at least 90% calibrated confidence, at least 95% measured precision and at least 20 tested suggestions among held-out predictions above that same 90% threshold for that field. It fills empty sender/type fields and adds at most three tags; manual choices, input rules, and removed tags stay in control. You can correct the result in the document dialog. With the option off, suggestions only appear in the dialog and need a tap.
- **Getting started:** it needs at least 3 hand-filed documents each for 2 or more senders (or types), or 3 documents with the same tag.
- **Privacy and restore:** each person's model uses only their own documents. The model is rebuilt rather than exported; the opt-in setting is included in portable exports. After a restore, automatic filing waits until the model is retrained.

### Workflows

Open **Workflows** to automate routine filing. A workflow runs:
- when a document is added (after its first processing);
- when you change a document;
- or each morning for documents a chosen number of days after their added date, document date, or follow-up due date.

**Conditions** are optional and can combine words in the title or OCR text, a tag, a sender, a type, a file-name pattern, and where the document came from.

**Actions** can:
- add or remove tags;
- set a sender or type, but never over one you chose yourself;
- mark the document as needing action;
- add a note;
- call a webhook;
- send an email.

**Run history:** added and scheduled workflows act once per document, and every run is listed with what it changed.

**Notifications:** webhooks and emails include the title, tags, sender, type, and a link, never the OCR text. An email attaches the original only when you tick the option, up to `RIPIANO_EMAIL_ATTACH_MAX_BYTES` (10 MB by default). Webhooks to private, loopback, or link-local addresses are refused unless `RIPIANO_WEBHOOK_ALLOW_PRIVATE=1`, for example for home automation on your LAN. Each webhook call has a 15-second limit. Notes, webhooks, and emails happen once per workflow and document, and "updated" workflows run only after title, date, sender, type, or tag changes. A completed follow-up is never reopened. A new scheduled workflow applies to documents that become due after it was created. Email needs `RIPIANO_SMTP_HOST`, `RIPIANO_SMTP_PORT`, `RIPIANO_SMTP_USER`, `RIPIANO_SMTP_PASSWORD`, `RIPIANO_SMTP_SECURITY` (`starttls`, `ssl`, or `none`), and `RIPIANO_SMTP_FROM`.

### Pages and versions

Open a document and choose **Open pages & versions**:
- **Edit pages:** rotate, remove, or reorder pages, then **Save as new version**. The previous file is kept as an older version, and the searchable PDF is rebuilt.
- **Split:** tick "New document after this page" and choose **Split into N documents**. This creates new documents and leaves the original untouched.
- **Merge:** in Library selection mode, **Merge into one PDF** creates a new document from the selected ones, in the order you selected them.
- **Upload a new version:** replace the current file with a corrected one.
- **Use an existing document:** search in **Pages & versions**, choose a ready document, and copy its current original as a new version. The source remains a separate document, while this document keeps its title, tags, and notes. Its previous file stays downloadable; active share links are revoked because their contents changed.
- **Older versions:** each can be downloaded or made current again. Making a version current adds a new version, so nothing is lost.
- **Signed PDFs:** a digitally signed PDF needs explicit confirmation before editing, because the edited version is no longer signed. The signed file remains as an older version.
- **Non-PDF originals:** page tools work on the searchable PDF.

Document exports include every older version. Only permanent deletion removes version files.

### Barcodes on paper scans

PDF and image scans are checked for QR codes and common 1D barcodes on the NAS. Nothing is sent elsewhere.
- **Separator sheets:** a sheet with the code `PATCHT` splits a multi-page PDF into separate documents and is itself dropped. The full scan is kept unchanged as the hidden source of its parts; open it from any part with **Open full scan**.
- **ASN:** a code such as `ASN00042` gives the document archive number 42. Numbers are unique per owner. A clash is recorded as a note on the document instead of being assigned, and you can change the number on the document. Search with `asn:42`.
- **Tags:** a code such as `TAG:Bills` adds your existing tag "Bills". In **Tags & filing**, you can also give a tag a unique barcode value (for example `ARCHIVE-BILLS`) and print its QR label. Put that label on a scan's first page to add the tag without exposing its name in the code. The mapping is per account, ignores letter case, and respects tags you manually removed from a document.

Set `RIPIANO_BARCODES=0` to turn this off. `RIPIANO_BARCODE_SEPARATOR`, `RIPIANO_BARCODE_ASN_PREFIX`, and `RIPIANO_BARCODE_TAG_PREFIX` change the codes. Up to 100 pages and the first 500 distinct non-control codes per file are checked (`RIPIANO_BARCODE_MAX_PAGES` controls pages). Physical-copy stickers remain a separate, stable identity for the paper itself.

### Optional email intake

Open **Email** in the app, connect a mailbox, then add a rule. A rule reads one folder and imports PDF, image, and Office attachments from messages that match its optional sender, subject, text, and file-name filters within a maximum age. After import it can mark the message read, flag it, move it, or leave it unchanged. Ripiano never deletes mail, and each message is handled once per rule even if the read flag is cleared. A rule can add tags, a sender, and a document type; phrase rules do not override them, and you can change them on the document. The maintenance worker checks mailboxes every `RIPIANO_MAIL_POLL_MINUTES` (default 5), and **Check now** runs a check immediately.

Use an IMAP app password where your provider offers one. Passwords and OAuth refresh tokens are encrypted with a key derived from `RIPIANO_SECRET_KEY`. Set `RIPIANO_MAIL_KEY` (a Fernet key) to keep them independent of that secret; changing either key requires entering mailbox passwords again.

Gmail and Outlook can use OAuth instead. Register a web OAuth client with the redirect URI `${RIPIANO_PUBLIC_ORIGIN}/api/mail/oauth/callback`, then set `RIPIANO_GMAIL_OAUTH_CLIENT_ID`/`_SECRET` (Google Cloud: Gmail API, scope `https://mail.google.com/`) or `RIPIANO_OUTLOOK_OAUTH_CLIENT_ID`/`_SECRET` (Microsoft Entra: delegated `IMAP.AccessAsUser.All` and `offline_access`). The matching **Sign in with Google/Microsoft** button appears only when its client is configured. Browser tests use a local GreenMail server: `docker compose -f deploy/compose.mailtest.yaml up -d`.

### Optional watched folder

Mount a NAS folder at `RIPIANO_WATCH_PATH`, set `RIPIANO_WATCH_OWNER_USERNAME` to an existing account, and start `docker compose --profile watch up -d`. The mount is read-only to Ripiano. Stable PDF, PNG, and JPEG files are copied into the archive and left in the incoming folder. The same path and bytes import once across restarts; changing a file creates a new document. Files above the configured 25 MB limit are skipped. Set `RIPIANO_WATCH_POLL_SECONDS` to adjust the default five-second poll.

The planning documents remain the implementation baseline. No Paperless source code is included in this repository.
