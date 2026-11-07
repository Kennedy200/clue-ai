# Clue AI

Open-source tool that turns scripts, ideas and long videos into captioned vertical shorts with AI voiceover.
Runs on your own laptop with one free key (OpenRouter). Not affiliated with any other product.

> **Status: feature complete for a first public release (v1.0 candidate).** Six video styles, Auto Clipping, the editor, billing (simulated),
> teams, brand kits, bulk, calendar, admin panel and Excel import/export all run and are tested. What is **not** verified is listed in
> [Honest limits](#honest-limits): AI features have never run against a real OpenRouter key, YouTube upload has never run against real Google,
> and the Docker deployment files have never been run. See [docs/PLAN.md](docs/PLAN.md).

## Quick start (Windows, macOS, Linux)

Requirements: Node 20+, Python 3.12, FFmpeg (`winget install Gyan.FFmpeg` on Windows).

```bash
npm run setup   # venv, Python + web deps, database, demo users
npm run dev     # API + worker + web, prints the links table
```

Open the printed App link. Paste your free OpenRouter key at `/setup` (sign in as the admin first; the admin and demo
passwords are printed on startup and saved to `storage/demo-credentials.json`). With no key, the app still boots and
every non-AI feature works.

## Check the AI features against your key

Save your OpenRouter key at `/setup` (sign in as admin), then run `npm run verify:llm`. It exercises script planning, ideas, title scoring, the enhancer and AI clip scoring with the real model and prints anything that fails. Until you do, those features have only been tested with fake providers.

## Optional voice plugins (Admin page)

Piper (more local voices: UK English, French, Spanish, Portuguese, Arabic, Swahili) and edge-tts (online Nigerian, Kenyan and South African English) are off by default. Read the licensing notes in `docs/PLUGINS.md` first.

## Modes

- `APP_MODE=self_host` (default): one owner, unlimited credits, emails go to the local dev inbox at `/dev-mail`.
- `APP_MODE=saas`: plan limits, free-plan credits and watermark.

## Why SQLite, and where Excel fits

SQLite (WAL mode) is the live database: zero cost, one file, safe for concurrent users and jobs. A spreadsheet is
not safe as a live store. Excel is the import / export / view layer (planned for the admin panel). The schema is
PostgreSQL-compatible.

## Tests

```bash
npm test
npm run scan   # secret scan, run before every push
```

## Deploy to a server (about 30 to 45 minutes)

A rented Linux server, a domain and Docker are all you need: `git clone`, copy `infra/.env.production.example` to `.env`, then `docker compose -f infra/docker-compose.yml --env-file .env up -d --build`. Caddy gets the HTTPS certificate by itself. Step by step, with backups, restore and troubleshooting: [docs/RUNBOOK.md](docs/RUNBOOK.md). Security notes and known gaps: [SECURITY.md](SECURITY.md). Costs and margins: [docs/COSTS.md](docs/COSTS.md).

Back up before every update: `python -m clue.backup create`. Restore: `python -m clue.backup restore <archive>`.

## Layout

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md). Plugins live in `plugins/<kind>/<name>/manifest.json`.

## Honest limits

- The AI features (ideas, script planner, title score, enhancer, Fix my hook, AI clip scoring) were tested with fake providers only. Run `npm run verify:llm` after saving your key.
- YouTube upload was tested against a mock of Google, not the real service.
- Lighthouse mobile performance for Home and Pricing measured 87 and 87 (median of three) on a slow laptop; accessibility 100. Not yet 90.
- Free OpenRouter models allow roughly 20 requests/minute and 50/day on an account that never bought credits.
- Payments are simulated by the built-in billing engine until you add a gateway plugin.
- The Docker/Caddy files have not been run on a real server by the author; the runbook says what to expect.
- Legal pages are templates: review with a lawyer before launch.

## License

MIT. See [LICENSE](LICENSE).

## Billing, referrals and Clue Score

Billing is built in and simulated (no real money moves). Open `/app/billing` to change plan, top up, view invoices and copy your invite link. `/app/score` scores a script for free. To take real payments, add a gateway plugin (see docs/PLUGINS.md). To test a declined card, set `prefs.sim_decline` on a user.
