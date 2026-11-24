# Ripiano

**A self-hosted document archive for any server: snap or upload a document, let Ripiano read it, find it again in seconds, and know where the paper original is.**

<p align="center">
  <img src="qa-artifacts/20261119-readme/desktop-library.png" alt="The Ripiano Library on desktop: a search bar, filters, and filed household documents with dates, senders, types, and tags" width="880">
</p>

<p align="center">
  <img src="qa-artifacts/20261119-readme/desktop-document.png" alt="An electricity bill open in Ripiano: first-page preview beside its title, date, sender, and type" width="620">
  &nbsp;
  <img src="qa-artifacts/20261119-readme/mobile-library.png" alt="The Ripiano Library on a phone" width="200">
</p>

## What it does

- **Scan or upload**: phone camera, photos, PDFs, Office files, and emails; the text is recognised automatically. The document opens with a short filing summary, task and paper actions; manual fields and portable exports stay one tap away. If text recognition is stopped, the Library and document view explain why the file is waiting; people opening a shared waiting document see the same problem and are asked to contact its owner.
- **Find anything fast**: search the words inside every document, or filter by sender, tag, type, or date.
- **Filing help**: matching rules and optional, locally learned automatic filing can add tags, senders, and document types. The learned automatic mode starts off; OCR search works before you configure any filing. Email suggestions ignore recurring recipient and header noise.
- **Dates that matter**: Ripiano can point out an explicit future payment deadline or event date in a document. You decide whether to save a task; **Add to calendar** downloads a local calendar file without an account connection.
- **Personal dashboard**: pin up to six live saved searches for bills, tickets, house papers, or anything else; see counts and recent matches, and optionally open the dashboard first on that device.
- **Paper originals**: keep a paper copy only when useful; Ripiano suggests a broad topic from an unambiguous matching tag, then gives it a sequential code such as `MED-00042`. Its QR label finds the document and its current location. Create a full path such as `Home / Shelf / Box` in one step, or move paper later without changing its sticker code. New paper labels omit the location so they stay accurate after a move; older labels that printed a location can be reprinted. Digital-only documents need no code, but an advanced option can reserve one for a paper copy you may keep later. ASN remains an optional barcode number for uploaded scans, separate from the paper sticker. Add or rename paper categories in the Paper archive; if you replace a mistaken label, the old QR still finds the copy. Old `R-…` and location labels still scan.
- **Works on your phone**: install it from the browser on iPhone or Android; an Android app adds a document scanner.
- **Family accounts**: everyone gets a private archive, and you can share single documents or send a link that expires. Optional document email shows the server's sending address before you send.
- **Automatic imports**: optionally pull in files from email, a mounted folder, cloud storage, or a Telegram bot.
- **Readable workflows**: choose a recipe, then configure it in a full-width editor with a live plain-language summary; optional conditions and specialist actions remain available.
- **Private and backed up**: everything stays on your server, with two-step sign-in and scheduled, checked backups. Security has separate, clearly labelled fields for changing your password; a change signs out other devices and revokes tokens, agents, and sharing links. Optional folder templates shape the readable browse copy without moving originals.
- **AI if you want it**: give an AI assistant limited, revocable access; Ripiano never sends your files to a paid AI service.

Original file bytes are synced before an upload completes. If a mounted filesystem rejects directory sync, Ripiano retries, completes the upload, and records a durability warning in server logs. Other storage I/O errors still fail the upload.

English and Italian interface. Full list: [user guide](docs/USER_GUIDE.md#features-at-a-glance) and [feature parity with Paperless-ngx](docs/FEATURE_PARITY.md).

## Install

You need Docker with the Compose plugin. The stack is defined in [`compose.yaml`](compose.yaml) and builds the images from source:

```sh
git clone https://github.com/p4xx07/ripiano.git
cd ripiano
cp .env.example .env   # set long random RIPIANO_SECRET_KEY, RIPIANO_SETUP_KEY, RIPIANO_DB_PASSWORD
docker compose up --build -d
```

Open <http://localhost:8080> and enter the `RIPIANO_SETUP_KEY` from `.env` to create the owner account. All settings are in the [user guide](docs/USER_GUIDE.md#install-and-run).

- **Pre-built images**: follow [deploy/README.md](deploy/README.md); it works with plain `docker compose` or any tool that runs Compose files.
- **Access from outside** behind one sign-in: see the [optional gateway example](deploy/gateway/README.md).

## Documentation

- [User guide](docs/USER_GUIDE.md): every feature, setting, and how-to, plus development commands.
- [Backup and restore](docs/BACKUP_RESTORE.md) (with the `/healthz` and `/livez` health checks) and [AI agent access (MCP)](docs/AGENT_ACCESS.md)
- [Android app](apps/android/README.md) and [architecture](docs/ARCHITECTURE.md)
- [Contributing](CONTRIBUTING.md) and [security policy](SECURITY.md)

**Status:** pre-release; see the [quality judges](docs/QUALITY_JUDGES.md) for what still blocks a release. Ripiano is an independent alternative to Paperless-ngx and includes none of its code. License: [LICENSE](LICENSE).
