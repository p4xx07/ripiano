# Ripiano

**A self-hosted document archive for your home server or NAS: snap or upload a document, let Ripiano read it, find it again in seconds, and know which shelf the paper original is on.**

<p align="center">
  <img src="qa-artifacts/20261119-readme/desktop-library.png" alt="The Ripiano Library on desktop: a search bar, filters, and filed household documents with dates, senders, types, and tags" width="880">
</p>

<p align="center">
  <img src="qa-artifacts/20261119-readme/desktop-document.png" alt="An electricity bill open in Ripiano: first-page preview beside its title, date, sender, and type" width="620">
  &nbsp;
  <img src="qa-artifacts/20261119-readme/mobile-library.png" alt="The Ripiano Library on a phone" width="200">
</p>

## What it does

- **Scan or upload**: phone camera, photos, PDFs, Office files, and emails; the text is recognised automatically. If text recognition is stopped, the Library and document view explain why the file is waiting; people opening a shared waiting document see the same problem and are asked to contact its owner.
- **Find anything fast**: search the words inside every document, or filter by sender, tag, type, or date.
- **Filing help**: matching rules and optional, locally learned automatic filing can add tags, senders, and document types. The learned automatic mode starts off; OCR search works before you configure any filing. Email suggestions ignore recurring recipient and header noise.
- **Personal dashboard**: pin up to six live saved searches for bills, tickets, house papers, or anything else; see counts and recent matches, and optionally open the dashboard first on that device.
- **Paper originals**: a QR sticker on each paper copy tells you which shelf or box it is in. Scan it with the phone camera (in Ripiano where the browser can read QR codes, or with the phone's camera app).
- **Works on your phone**: install it from the browser on iPhone or Android; an Android app adds a document scanner.
- **Family accounts**: everyone gets a private archive, and you can share single documents or send a link that expires.
- **Automatic imports**: optionally pull in files from email, a NAS folder, cloud storage, or a Telegram bot.
- **Private and backed up**: everything stays on your server, with two-step sign-in and scheduled, checked backups.
- **AI if you want it**: give an AI assistant limited, revocable access; Ripiano never sends your files to a paid AI service.

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

- **NAS with pre-built images**: follow [deploy/README.md](deploy/README.md); it works with plain `docker compose` or any tool that runs Compose files.
- **Access from outside** behind one sign-in: the [Raspberry Pi gateway](deploy/gateway/README.md).

## Documentation

- [User guide](docs/USER_GUIDE.md): every feature, setting, and how-to, plus development commands.
- [Backup and restore](docs/BACKUP_RESTORE.md) (with the `/healthz` and `/livez` health checks) and [AI agent access (MCP)](docs/AGENT_ACCESS.md)
- [Android app](apps/android/README.md) and [architecture](docs/ARCHITECTURE.md)
- [Contributing](CONTRIBUTING.md) and [security policy](SECURITY.md)

**Status:** pre-release; see the [quality judges](docs/QUALITY_JUDGES.md) for what still blocks a release. Ripiano is an independent alternative to Paperless-ngx and includes none of its code. License: [LICENSE](LICENSE).
