# External access gateway (Raspberry Pi)

One front door for every self-hosted service: **Traefik** receives all traffic from the internet, gets HTTPS certificates, asks **Authelia** whether you are signed in, and forwards the request to the right service on the NAS. Decision record: [D3 in docs/DECISIONS.md](../../docs/DECISIONS.md).

```
Internet ─80/443─▶ Router ─▶ Raspberry Pi 4
                               ├─ Traefik  (certificates, routing)
                               │    └─ not signed in? ─▶ Authelia login at auth.<domain>
                               ├─ ripiano.<domain>  ─▶ http://NAS_IP:8080
                               └─ jellyfin.<domain> ─▶ http://NAS_IP:8096
```

- **Subdomains**, one per service. Your wildcard DNS record already points every subdomain at your home IP.
- **One sign-in for all services** (a cookie for the whole domain). Tick **Remember me** on your own devices to stay signed in for 30 days.
- **Ripiano keeps its own accounts.** Authelia is only a door: you sign in to Authelia, then to Ripiano (both sessions persist).
- **Resources:** two containers capped at 128 MB RAM each (in practice about 30–50 MB each). Nothing runs on the NAS.

## Files

| File | Purpose |
| --- | --- |
| `compose.yaml` | Traefik + Authelia |
| `gateway.env.example` | Copy to `.env`: domain, NAS address and ports, certificate email |
| `traefik/dynamic/routes.yml` | Which subdomain goes where, and which requests skip the sign-in |
| `authelia/configuration.yml` | Sign-in rules: two-step sign-in for every subdomain, session lengths, lockout |
| `authelia/users.example.yml` | Copy to `users.yml`: the people who may sign in |

`.env`, `secrets/`, `data/`, and `authelia/users.yml` stay on the Pi and are never committed.

## Before you start

- Raspberry Pi 4 with a 64-bit OS (`uname -m` prints `aarch64`), Docker, and the Compose plugin. Boot from an SSD if you can; SD cards wear out.
- In the router, give the **Pi** and the **NAS** fixed addresses (DHCP reservation).
- **Pi-hole on the same Pi uses ports 80 and 443 for its own admin page.** Move it first, or Traefik cannot start:
  - Pi-hole v6 installed directly: `sudo pihole-FTL --config webserver.port '8081o,[::]:8081o'`. The admin page moves to `http://<Pi IP>:8081/admin`.
  - Pi-hole in Docker: change its port mapping (for example `8081:80`) and remove any `443` mapping.

## Setup

1. **Copy this folder to the Pi**, for example to `~/gateway`, and open a shell there.
2. **Settings:** `cp gateway.env.example .env`, then edit `.env`: `DOMAIN`, `NAS_IP`, the ports, and `ACME_EMAIL`.
   On the NAS, set `RIPIANO_TRUSTED_PROXIES` to the Pi's fixed LAN address in the Ripiano stack's environment and redeploy, so Ripiano throttles failed sign-ins per person instead of for everyone coming through the Pi.
3. **Secrets** (random values Authelia uses to sign and encrypt):
   ```sh
   mkdir -p secrets
   for name in jwt_secret session_secret storage_encryption_key; do openssl rand -hex 64 > "secrets/$name"; done
   chmod 600 secrets/*
   ```
   Keep `storage_encryption_key`. Without it, Authelia cannot read the saved two-step devices.
4. **Your account:**
   ```sh
   cp authelia/users.example.yml authelia/users.yml
   docker run --rm -it authelia/authelia:4.39.4 authelia crypto hash generate argon2
   ```
   Type the password when asked, then paste the `$argon2id$...` line into `users.yml` as the `password` value. Set your display name and email.
5. **Pin the images.** Check for newer patch releases first ([Traefik](https://github.com/traefik/traefik/releases), [Authelia](https://github.com/authelia/authelia/releases)), then pin the exact build:
   ```sh
   docker buildx imagetools inspect traefik:v3.5.3 --format '{{json .Manifest.Digest}}'
   docker buildx imagetools inspect authelia/authelia:4.39.4 --format '{{json .Manifest.Digest}}'
   ```
   In `compose.yaml`, write each image as `traefik:v3.5.3@sha256:...` with the printed value.
6. **Start:** `docker compose up -d`, then `docker compose logs -f`. Authelia should print `Listening for non-TLS connections on '[::]:9091'`, and Traefik should print no `ERR` lines about routers.
7. **Router (Vodafone Power Station):** in the port forwarding / port mapping section (the name varies by firmware), forward **TCP 80** and **TCP 443** to the Pi's address. Remove the old 80/443 forwards to the NAS.
8. **Certificates:** Traefik requests one certificate per subdomain on first visit. It needs port 80 reachable from the internet. Check with `docker compose logs traefik | grep -i acme`. Certificates renew automatically.
9. **Two-step sign-in:** open `https://auth.<domain>`, sign in, and choose to register a one-time-password device. No email server is configured, so the confirmation link is written to a file on the Pi:
   ```sh
   cat data/authelia/notification.txt
   ```
   Open that link and scan the QR code with an authenticator app.

## Ripiano settings

- In the Ripiano stack's environment, set `RIPIANO_PUBLIC_ORIGIN=https://ripiano.<domain>` and `RIPIANO_ALLOWED_HOSTS=ripiano.<domain>`.
- **Android app:** on the server screen, enter the Ripiano address and, under **Sign-in address**, `https://auth.<domain>`. The Authelia page then opens inside the app and its cookie stays there. See [apps/android/README.md](../../apps/android/README.md).
- These requests **skip the Authelia sign-in**, because Ripiano checks them itself:
  - share links and share bundles (`/api/share-links/…`, `/api/share-bundles/…`), so people without an account can download what you shared;
  - the PWA manifests and icons, which browsers fetch without cookies;
  - MCP agents (`/mcp` with `Authorization: Bearer …`) and personal API tokens (`/api/…` with `Authorization: Token rip_…`). A token header does not open any page.
- Ripiano's sign-in throttling sees the Pi's address for every outside request, so all outside clients share one limit. Authelia's lockout (5 failures in 10 minutes → 30-minute ban) runs first.

## Jellyfin

- Web browsers go through the Authelia sign-in like Ripiano.
- TV and phone apps cannot show a web sign-in. Requests carrying Jellyfin's own authorization headers (`Authorization: MediaBrowser …`, `X-Emby-Authorization`, `X-Emby-Token`, `X-MediaBrowser-Token`) skip Authelia and are checked by Jellyfin. Use strong Jellyfin passwords.
- In Jellyfin → Dashboard → Networking, add the Pi's address under **Known proxies**, so Jellyfin sees real client addresses.

## Using the domain at home (Pi-hole)

Inside your home, `ripiano.<domain>` must point to the Pi, not to your public IP. Point every subdomain at the Pi with one DNS line:

- Pi-hole v6: `sudo pihole-FTL --config misc.dnsmasq_lines '["address=/<domain>/<Pi IP>"]'`
- Older Pi-hole: put `address=/<domain>/<Pi IP>` in `/etc/dnsmasq.d/99-gateway.conf` and run `pihole restartdns`.

Then make your devices use the Pi as DNS server: set the Pi's address as DNS in the router's DHCP settings. If the Power Station does not let you change the DNS server it hands out, turn off DHCP in the router and enable Pi-hole's DHCP server instead (Pi-hole → Settings → DHCP).

## Add another service

In `traefik/dynamic/routes.yml`, add a router and a service. Traefik applies the change on save:

```yaml
    photos:
      rule: Host(`photos.{{ env "DOMAIN" }}`)
      entryPoints: [websecure]
      middlewares: [hsts, authelia]
      service: photos
      priority: 10
# under services:
    photos:
      loadBalancer:
        servers:
          - url: http://{{ env "NAS_IP" }}:2342
```

Keep multi-line rules at the same indentation on every line, or Traefik rejects them.

## Roll back

Point the router's 80/443 forwards back to the NAS. The Synology reverse proxy and its wildcard certificate work as before. Then run `docker compose down` on the Pi.

## Known limits

- If the Pi is off, nothing is reachable from outside. Services still work at home by NAS address and port.
- Services on the NAS remain reachable on your home network without the Authelia sign-in (by `NAS_IP:port`). Ripiano and Jellyfin still require their own sign-in.
- Self-service password reset is off (no email server). Reset a password by generating a new hash (step 4) and editing `users.yml`; Authelia reloads the file.

## What was tested

On 2026-11-17, this exact configuration (`traefik:v3.5.3`, `authelia/authelia:4.39.4`) ran locally with a test backend standing in for the NAS:

- Pages and `/api` without a token redirect to `https://auth.<domain>/`.
- Share links, share bundles, manifests, and icons reach Ripiano.
- `/mcp` with a `Bearer` token and `/api` with a `Token` header reach Ripiano; a token on `/`, a `Bearer` token on `/api`, and Basic auth are refused or redirected.
- Jellyfin redirects browsers and lets requests with Jellyfin app headers through.
- The Authelia portal answers.

Not yet tested: Let's Encrypt issuance (needs the real domain and router), a full sign-in with two-step verification, and the Android app on a phone.
