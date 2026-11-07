# Runbook

For the person who runs the server. Every command is copy-paste. "Self-host" means your own computer; "VPS" means a rented Linux server with Docker.

## Deploy to a fresh VPS (about 30 to 45 minutes)

You need: a Linux VPS with 4 vCPU and 8 GB RAM or more (Ubuntu 22.04 or 24.04), a domain name, and about 15 GB of disk for models and videos.

1. **Point your domain at the server.** In your domain provider, add an `A` record: `clue.yourdomain.com` -> the server's IP address. Wait a few minutes.
2. **Install Docker** (on the server):
   ```bash
   curl -fsSL https://get.docker.com | sh
   ```
3. **Get the code:**
   ```bash
   git clone https://github.com/Kennedy200/clue-ai.git && cd clue-ai
   ```
4. **Configure:**
   ```bash
   cp infra/.env.production.example .env
   nano .env        # set DOMAIN, ADMIN_EMAIL and the SMTP_* lines; paste your OpenRouter key if you have it
   ```
5. **Open the firewall** for ports 80 and 443 only (`ufw allow 80,443/tcp && ufw enable`; also allow SSH first: `ufw allow OpenSSH`).
6. **Start:**
   ```bash
   docker compose -f infra/docker-compose.yml --env-file .env up -d --build
   ```
   The first build takes 5 to 10 minutes.
7. **Download the local voice and speech models once** (they live in the data volume and survive restarts):
   ```bash
   docker compose -f infra/docker-compose.yml exec api python -m clue.core.models_dl
   ```
8. **Open `https://clue.yourdomain.com/signup`** and sign up with the email you put in `ADMIN_EMAIL`. Click the verification link in the email (this needs the SMTP settings from step 4; without SMTP the message only lands in the local dev inbox, which is switched off outside self-host mode, so set SMTP before you invite anyone). After verifying, that account is the admin.
9. Go to `/setup` or Admin > Integrations and save your OpenRouter key.

The API and worker are never exposed to the internet; only Caddy listens on 80/443 and gets the HTTPS certificate itself.

> Status: the Docker files have **not been run** by the author (no Docker on the build machine). Expect to fix one or two small things the first time, and please send them back as an issue.

## Everyday commands

```bash
docker compose -f infra/docker-compose.yml ps                 # what is running
docker compose -f infra/docker-compose.yml logs -f api       # live logs (also: worker, web, caddy)
docker compose -f infra/docker-compose.yml restart worker     # restart one service
git pull && docker compose -f infra/docker-compose.yml --env-file .env up -d --build   # update
```

Database changes run by themselves when the API starts (`alembic upgrade head`). **Take a backup before every update.**

## Backups (do this before you need it)

Create a backup (safe while the app is running):

```bash
docker compose -f infra/docker-compose.yml exec api python -m clue.backup create --out /data/backups
# local install:  .venv/Scripts/python -m clue.backup create     (from apps/api)
```

The archive holds the database, the encryption secret and every user's videos and uploads, with checksums. **It contains your secret key: keep it private**, copy it off the server (for example `scp` to your laptop, or rclone to a storage bucket). Skip the large media with `--no-media` for a small database-only copy.

Check a backup without restoring it:

```bash
python -m clue.backup verify clue-backup-YYYYMMDD-HHMMSS.tar.gz
```

Schedule it daily on the server (`crontab -e`):

```
15 3 * * * cd /home/ubuntu/clue-ai && docker compose -f infra/docker-compose.yml exec -T api python -m clue.backup create --out /data/backups && find /var/lib/docker/volumes/clue_clue_data/_data/backups -name "clue-backup-*" -mtime +14 -delete
```

## Restore

1. Stop the app: `docker compose -f infra/docker-compose.yml stop api worker web`
2. Restore (the archive is checked first; the existing data is moved aside, never deleted):
   ```bash
   docker compose -f infra/docker-compose.yml run --rm api python -m clue.backup restore /data/backups/clue-backup-XXXX.tar.gz
   ```
   Local install: `python -m clue.backup restore path\to\archive.tar.gz`.
3. Start again: `docker compose -f infra/docker-compose.yml up -d`
4. Sign in and check a video plays and a balance looks right.

The restore is covered by automated tests (`apps/api/tests/test_backup.py`): the ledger sum, the files and the secret all come back, a damaged archive is refused before anything is touched, and unsafe paths in an archive are rejected. It has **not** yet been rehearsed on a real server; do one trial restore on a spare machine before you rely on it.

**Postgres** (if you set `DATABASE_URL` to Postgres): use `pg_dump` for the database and copy the `files` and `.secret` from the data folder yourself; `clue.backup` only handles SQLite.

## When something is wrong

| Symptom | Check |
|---|---|
| Site will not load | `docker compose ... ps`, then `logs caddy`. Is the domain pointing at the server? Ports 80 and 443 open? |
| Videos stay "queued" | The worker is down: `logs worker`, `restart worker` |
| "AI is not set up yet" | No OpenRouter key saved. Add it at `/setup` |
| "AI quota reached" | Free models allow about 50 requests per day per account. Wait, or add credits to your OpenRouter account |
| Renders are very slow | Server is busy or small. `docker stats`. Cinematic and long Auto Clipping are the heavy jobs |
| Disk full | Videos and uploads grow. Delete old backups, then see "Disk" below |
| Everyone gets "Too many attempts" | The proxy is not passing the client address. Check `TRUST_PROXY=true` and that only Caddy reaches the API |
| Forgot the admin password | Use "Forgot password" with the admin email |
| A user was charged but the video failed | Credits are refunded automatically on a final failure. If one was missed, Admin > Users > Credits, with a reason (it is logged) |

**Disk:** `docker system df`; `docker compose ... exec api du -sh /data/*`. Finished videos live in `/data/files/<user>/`.

## Monitoring

- `GET /api/health` returns `{"ok": true}`; point an uptime checker (UptimeRobot is free) at `https://DOMAIN/api/health`.
- Admin > Overview shows jobs by status, AI cost per feature and per finished video.
- If many jobs show `failed`, read `logs worker`.

## Billing is simulated

Until a payment-gateway plugin replaces `Gateway` in `clue/core/billing.py`, upgrades and top-ups succeed without moving money. Do not take real customers on a paid plan until you add one (see `docs/PLUGINS.md`).
