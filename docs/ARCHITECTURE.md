# Clue AI — Architecture

## Processes (local, no Docker)

```
Browser ──► Next.js :3000 ──(/api/* rewrite)──► FastAPI :8000 ──► SQLite (WAL) ./storage/clue.db
                                                    │
                                   job rows ◄───────┴──────► Worker (python -m clue.worker)
                                                              ├─ FFmpeg (render, procedural loops)
                                                              ├─ faster-whisper (CPU, int8)
                                                              ├─ Kokoro / Piper (TTS)
                                                              └─ LLM provider (OpenRouter)
```

`npm run dev` starts all three and prints the links table.

## Repo map

```
apps/web        Next.js (App Router)
apps/api        FastAPI + worker, python package `clue`
  clue/api      routers
  clue/core     config, db, security, settings store
  clue/ai       llm providers, prompts, scoring
  clue/render   scene json, ffmpeg compiler
  clue/jobs     queue + handlers
  clue/plugins  discovery + registry
packages/brand  SVG logo pack, tokens
plugins/<kind>/<name>/manifest.json
scripts/        setup.mjs, dev.mjs, secret-scan.mjs
content/        blog MDX, features.json
data/           seed xlsx
docs/
```

## Key decisions

- **SQLite + WAL** as live store; PG-compatible schema (ULID text PKs, UTC timestamps, no SQLite-only SQL). Excel is the import/export/view layer.
- **Job queue**: `jobs` table; workers claim with an atomic `UPDATE ... WHERE status='queued'` inside a transaction (safe against double-claim); priority by plan; attempts ≤ 2.
- **Credits**: append-only `credit_ledger`; reserve → settle/refund; balance = SUM(ledger), never negative (checked in the same transaction).
- **Scene JSON** is the single source of truth for both browser preview and FFmpeg compiler.
- **Plugins**: kinds = `llm, tts, asset, payment, email, storage, publisher, caption_style, template, niche_pack`. Discovered at startup from `plugins/`, config forms generated from `manifest.json`.
- **Secrets**: OpenRouter key stored encrypted (Fernet, key derived from a local secret file `storage/.secret`) in `settings`; `.env` also supported; never logged.
- **Security**: argon2id, httpOnly SameSite=Lax cookies, CSRF token header, FFmpeg args as arrays only, user text escaped before drawtext/ASS, transcripts wrapped as data in prompts.
- **Modes**: `APP_MODE=self_host|saas`.
