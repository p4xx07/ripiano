# Ripiano product specification

Status: implementation baseline, 2026-11-04. Reference: Paperless-ngx v3.4.2.

## Product promise

A document should normally be filed as soon as it is captured or imported. The Inbox is for exceptions that need a human decision, not a mandatory second stage for every document. Documents remain on the user's NAS and are searchable by their contents and metadata. A document may be digital only or have one or more tracked physical copies.

## Users and deployment

- A household or small team with separate user accounts, groups, and document-level access.
- A Synology DS923+ running a Portainer Docker Compose stack. The same HTTPS origin serves the PWA and API, following Condivisa's deployment shape. Heavier processing runs in separate containers.
- iPhone/iPad: installable Safari PWA. Android: installable PWA and an Android client with the same functions plus a native scanner. Desktop browser: full management interface.
- The archive starts empty. A Paperless migration is useful later but is not an initial dependency.
- Tailscale may provide private remote access. A public internet endpoint is not required for a PC-hosted MCP client that can reach the NAS over the tailnet.

## Navigation and interaction

Primary destinations: **Inbox**, **Library**, **Places**, and **Settings**. **Add document** is always prominent. Desktop navigation may expose additional administration shortcuts; mobile keeps the daily actions in a bottom bar. Use Condivisa's clear primary action, readable cards, responsive layouts, and light/dark support, with Ripiano's own deep-green, warm-paper, graphite, and amber visual identity.

Common operations must have direct, understandable controls. Advanced search, workflow editing, permissions, versions, and PDF tools remain reachable in context. The app must not require users to create special Inbox/TODO tags or saved views to make the basic workflow function.

### Capture and filing

1. User taps Add and chooses camera, Photos/Gallery, Files, share sheet, drag-and-drop, email, scanner folder, or API.
2. Ripiano immediately saves an immutable original and creates a durable processing job. The UI shows upload and processing state, errors, and retry options. No metadata is required before saving.
3. Text is extracted or OCR'd; an archive PDF/A and preview are generated where supported. Rules and local classification propose a title, issued date, correspondent, type, tags, and storage path. Each proposal records its source and evidence.
4. High-confidence, calibrated decisions are applied automatically. Uncertain, conflicting, duplicate, or failed items appear in Inbox with one-screen correction. Users can defer a decision without losing the document.
5. If the user keeps paper, they choose **Keep physical copy** during capture or later, assign a location and sticker, and confirm placement. Digital-only items do not require a physical step.

The Android client must support multi-page capture, crop, rotation, page order, gallery import, PDF output, and an upload draft that survives app interruption. Use a native scanner bridge; the PWA has camera-picker, Photos/Gallery, and Files paths. Test installed PWAs on real iOS and Android devices. HTTPS is required for browser camera APIs. A camera failure must leave file import usable.

### Search and retrieval

- Search across title, OCR text, notes, tags, correspondent, type, dates, custom fields, barcode/ASN, and physical sticker code.
- Show useful snippets and filters; preserve advanced query syntax through an explicit query parser.
- Search results identify whether the file is digital only or where its physical copy is stored.
- Scanning a sticker opens the corresponding document or container. A readable code is printed alongside the QR/barcode.
- Users can create saved collections, but the basic Library works without setup.

### Documents and physical copies

- Preserve original files, derived archive files, text, preview, audit history, and versions. Edits that change file contents create a version or require an explicit warning about signature invalidation.
- A document can have zero or more physical copies. Each copy has its own stable sticker ID, current location, and movement history. Locations form a hierarchy such as room > shelf > box/binder.
- Tags describe subject matter. A physical sticker identifies a copy; it does not replace tags. File storage paths are implementation choices or export layouts, not the user's filing task.
- Provide printable sticker sheets, container labels, a label reprint path, and a lost/moved state.

### Actions and automation

- **Needs action** is a first-class state with optional due date and reminder, not a special tag users must create.
- Provide readable automation recipes, then an advanced condition/action editor for parity with Paperless workflows. Rules may react to import, add, update, and schedule events.
- Duplicate detection shows exact and likely duplicates before merge; no automatic deletion of originals.
- Optional local or remote LLM assistance is explicit. Remote models never receive content without a user-configured provider and action.

## Agent experience

**Connect agent** creates a separate named grant for each client, such as `Local filing worker`, `Codex on desktop`, or another MCP-capable agent. The user authenticates to Ripiano and approves the grant; the agent does not receive the user's password. A single user may have multiple agents with different permissions, document scopes, expiry, and revocation. Activity displays the agent identity and action.

Agent access is optional and cannot be required for daily capture, search, or routine filing. A scheduled personal-computer worker may classify pending documents through MCP; the archive queue remains durable while it is offline. A work-managed computer cannot be assumed private from its employer even if the model and network connection are local.

## Backup and recovery

Ripiano schedules complete, restorable backups to a Portainer-mounted backup volume: database, original and derived documents, physical locations, grants/configuration needed for restore, and a versioned manifest with checksums. Write to staging, verify, then mark a snapshot complete. Show last success/failure, retention, space use, and restore instructions. Test restoring to a clean stack. The user configures Synology Hyper Backup and Backblaze B2 outside Ripiano.

## Release acceptance

- A new document can be captured and safely stored without entering metadata or visiting Inbox.
- Low-confidence classification goes to a short review queue with evidence and one-tap correction; the original remains intact.
- Every Paperless baseline capability has a tracked parity row and a test or documented manual scenario before the parity milestone is declared complete.
- A permitted user can locate both the digital document and its physical copy; an unauthorized user or agent cannot.
- Repeating an upload/worker job after interruption does not silently lose, duplicate, or corrupt a document.
- A backup can restore a clean installation, including sticker locations and agent grants. Revoked grants stay revoked after restore.
- Real iOS PWA, Android PWA, and Android client capture scenarios pass on representative devices. No claim of universal camera compatibility is made.
