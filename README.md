# Clue AI

Open-source tool that turns scripts, ideas and long videos into captioned vertical shorts with AI voiceover.
Runs on your own laptop with one free key (OpenRouter). Not affiliated with any other product.

> **Status: early development (Phase 5 of 8).** Accounts, the marketing site, the job queue, credits, local voice (Kokoro), word-synced captions
> and the FFmpeg renderer work through the API (Text Story). The web UI for creating videos, the other styles and the editor are not built yet.
> See [docs/PLAN.md](docs/PLAN.md).

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

## Layout

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md). Plugins live in `plugins/<kind>/<name>/manifest.json`.

## Honest limits

- Free OpenRouter models allow roughly 20 requests/minute and 50/day on an account that never bought credits.
- Payments are simulated by the built-in billing engine until you add a gateway plugin.
- Legal pages are templates: review with a lawyer before launch.

## License

MIT. See [LICENSE](LICENSE).
