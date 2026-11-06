# Clue AI — PLAN

Source of truth: the owner's master build prompt (sections 0–16). This file tracks phases, decisions, risks and deviations. Checkboxes are updated at the end of every phase.

## 1. Environment (verified 2026-11-06)

| Tool | Status |
|---|---|
| Node | v24.22.0 (OK) |
| Python | 3.12.10 (OK) |
| Git | 2.55 (OK) |
| FFmpeg / ffprobe | missing → installing via `winget install Gyan.FFmpeg` |
| GitHub CLI (`gh`) | missing → owner must install (`winget install GitHub.cli`) and run `gh auth login` before repo creation |
| Docker | missing → optional path only; not needed locally |

## 2. Architecture summary (details in ARCHITECTURE.md)

- `apps/web` Next.js App Router + TS strict + Tailwind; browser talks to API same-origin via `/api/*` rewrites.
- `apps/api` FastAPI + SQLAlchemy 2 + Alembic on SQLite (WAL), PG-compatible. Package `clue`. API process and worker process share the code.
- DB-backed job queue (no Redis). SSE for progress.
- Everything optional is a plugin in `plugins/<kind>/<name>/manifest.json`.
- Local-first: OpenRouter (free models) for LLM, Kokoro/Piper for TTS, faster-whisper for STT, FFmpeg for render and procedural backgrounds, Pollinations + Wikimedia for imagery. No other account is required.

## 3. Phases

- [x] **Phase 0 – Plan**: PLAN.md, ARCHITECTURE.md, tool check, git init.
- [~] **Phase 1 – Foundation** (done except GitHub repo: `gh` missing; see report): monorepo scripts (`npm run setup`, `npm run dev`, links table), DB + migrations, auth, design tokens, brand SVGs, app shell, CI, GitHub repo (needs `gh`).
- [ ] **Phase 2 – Marketing site**: Home, Pricing, features hub + pages, blog, legal, SEO.
- [ ] **Phase 3 – Core pipeline**: queue, storage, LLM wrapper + prompts, TTS, STT, asset providers, Scene JSON, FFmpeg renderer (Fast), SSE.
- [ ] **Phase 4 – Styles + tools**: 6 styles, standalone tools, Auto Clipping.
- [ ] **Phase 5 – Editor**: preview, timeline, panels, captions, autosave, mobile layout, Pro/Cinematic.
- [ ] **Phase 6 – Money**: ledger, plans, internal billing, invoices, referrals, Clue Score + Clue Card.
- [ ] **Phase 7 – Teams, brand kits, bulk, YouTube publish, analytics, admin, xlsx.**
- [ ] **Phase 8 – Hardening**: security, perf, a11y, backups, runbook, COSTS with measured numbers, e2e.

## 4. Task breakdown per role (Phase 1 focus)

- Backend-1: settings table (encrypted), auth (argon2id, sessions, CSRF), users/plans/ledger models, Alembic baseline.
- Backend-2: `LLMProvider` + OpenRouter, free-model discovery/fallback, prompt library skeleton.
- Backend-3: job queue table + worker loop, storage provider, ffprobe/ffmpeg wrappers.
- Frontend-1/2: design tokens, layout shell, `/setup`, auth pages.
- Brand: SVG mark, wordmark, favicons.
- DevOps/Automation: `scripts/setup.mjs`, `scripts/dev.mjs` (cross-platform), CI workflow, `.gitignore`, `.env.example`.
- QA: pytest scaffold, secret-scan script.

## 5. Risk log

| # | Risk | Mitigation |
|---|---|---|
| 1 | OpenRouter free quota is tiny (50 req/day unfunded) | One LLM call per video, content-hash cache, quota meter, graceful degrade |
| 2 | Kokoro/Piper/faster-whisper model downloads are large on Nigerian bandwidth | Resumable downloads in setup, models optional until first use, size shown beforehand |
| 3 | Windows path/shell differences | Node scripts only, no bash-only syntax, paths via `pathlib`/`path` |
| 4 | Pollinations anonymous tier slow/watermarked | Queue + cache, procedural/uploaded fallback, never block render |
| 5 | Scope is very large | Strict phase order; each phase must run end-to-end before the next |
| 6 | Python 3.12 wheels for kokoro/onnx on Windows | Use `kokoro-onnx` / `piper-tts` with pinned versions; verify in Phase 3 |
| 7 | `gh` missing, so repo creation blocked | Tell owner; continue locally |

## 6. Deviations (honest notes)

- The master prompt file was not present on disk, so it is not copied into the repo; this PLAN is derived from it. Re-add it as `BUILD_PROMPT.md` if wanted.
- Working directory is `Clue AI` (with a space) rather than `clue-ai`; the git repo name on GitHub will still be `clue-ai`. Scripts must quote paths.
- Section 3A overrides sections 5.3/5.9 (OpenRouter default, internal billing). Anthropic SDK is an optional plugin only.

## 7. Phase reports

_(appended at the end of each phase)_

### Phase 1 report (2026-11-06)

Built and run: `npm run setup` and `npm run dev` on Windows (links table prints, RUNNING.md written), FastAPI + SQLite/WAL + Alembic baseline, auth (signup/login/logout/verify/forgot/reset/change/delete/export, CSRF, lockout, rate limits), encrypted settings store, `/setup` OpenRouter key page (key test hits OpenRouter, not yet exercised with a real key), OpenRouter provider with free-model discovery/fallback/cache/usage logging, credits ledger, DB job queue + worker, plugin discovery, dev inbox, brand mark + lockup SVG, CI workflow.
Verified: 16 pytest tests green (auth flow, lockout, referral, credits reserve/settle/refund, concurrent claim, retries, no-key error); web type-check clean; all pages return 200 through the Next proxy; signup/me/dev-mail confirmed via curl.
Not yet done: GitHub repo (needs `gh`), PNG/OG brand assets, shadcn/Framer/TanStack wiring, browser screenshots at 360/1280 px, Playwright, Docker files, LLM path tested against a live key.
Deviation: the first-run key page is only open before any user exists; because seed creates demo users, the owner signs in as admin first. Revisit in Phase 8.
