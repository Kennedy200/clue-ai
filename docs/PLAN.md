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
- [~] **Phase 2 – Marketing site** (built and measured; Lighthouse 90 target not yet met): Home, Pricing, features hub + pages, blog, legal, SEO.
- [x] **Phase 3 – Core pipeline** (verified; see report): queue, storage, LLM wrapper + prompts, TTS, STT, asset providers, Scene JSON, FFmpeg renderer (Fast), SSE.
- [~] **Phase 4 – Styles + tools** (built and e2e-tested; AI-dependent paths unverified against a live key): 6 styles, standalone tools, Auto Clipping.
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

### Phase 2 report (2026-11-06)

Built: home (hero animation, steps, styles, tools, Clue Score teaser, DB-driven reviews with empty state, 16-question FAQ + JSON-LD), pricing (annual default 50% off, NGN/USD toggle with NG locale detect, plans from API with fallback), features hub + 23 pages from `content/features.json` (20 features + 3 fair comparisons, no third-party names), blog (6 original posts, 1,039-1,197 words each, no invented statistics, RSS), about, contact (saves a ticket and emails admin), privacy/terms/refund, 404, sitemap, robots, skip link, Organization/FAQ/Breadcrumb/Article JSON-LD. API: `/api/contact`, `/api/reviews`, `/api/plans`; migration 0002; 18 tests pass.
Verified by running: all 16 marketing routes return 200 (unknown route 404), contact form saves and mails, `next build` passes with type-check, first-load JS 103-108 kB.
Lighthouse mobile (production build, local Chrome): raw defaults (4x CPU slowdown) home 84 / pricing 65; accessibility 96/100, SEO 100/92 (canonical fixed afterwards with metadataBase, not re-measured). This laptop (i5-6300U, benchmarkIndex ~600) is slower than Lighthouse's reference, and at 2x slowdown the scores were 89 / 87. **The >=90 target is therefore NOT met**; TBT (420-480 ms) is mostly React/Next hydration. Revisit in Phase 8 on faster hardware or with further JS cuts.
Not done: blog is plain Markdown rendered by a tiny renderer, not MDX (deviation, avoids a dependency); PNG/OG images and favicons; browser screenshots at 360/1280 px; Playwright; a11y audit beyond Lighthouse; legal pages are templates (review with a lawyer).
Note: an orphaned API process from the first dev session still holds port 8000; the current stack uses 8001.

### Phase 3 report (2026-11-06)

Built and run for real: storage with signed expiring links and path-traversal protection; FFmpeg/ffprobe wrappers (argument arrays only); Scene JSON (pydantic); renderer (per-scene segments, procedural gradient backgrounds, Ken Burns on images, looped video, ASS word-highlight captions with sanitised user text, watermark, loudness normalisation, 48 kHz AAC, faststart); Kokoro TTS (54 voices, local, keyless; model downloaded and resumable); faster-whisper word alignment with proportional fallback; Text Story job (reserve credits first, then enqueue; settle on success; refund on final failure or cancel); SSE progress; signed downloads; one-call LLM planner (script + scenes + keywords + hook + title; provider-neutral, injection-safe, cached, one repair retry, max 3 models, no tight loops); keyless Wikimedia (licence/author captured, NC/ND skipped) and Pollinations providers.
Verified: 39 pytest tests green (golden render with ffprobe assertions, credits across success/fail/cancel/insufficient, queue, planner with fake provider, asset parsing); a real 12 s video rendered with Kokoro + Whisper; frames inspected visually (captions, highlight, Ken Burns on real images); full HTTP flow through the Next proxy as the demo user (login, create, live SSE progress, signed download, ffprobe: 1080x1920 H.264/AAC).
Bugs found by running it and fixed: `.local` demo/admin logins were rejected by email validation (Phase 1 bug); `python -m clue.worker` never saw its handlers (module imported twice) so jobs stayed queued; Wikimedia NC/ND licence filter missed "CC BY-NC"; audio came out at 96 kHz; uvicorn `--reload` hangs on Windows, so it is now opt-in (`API_RELOAD=1`); whisper's PyAV decode failed, so audio is decoded with our FFmpeg.
NOT covered yet: the LLM planner has never run against a real OpenRouter key (tests use a fake provider); Pro/Cinematic modes and music ducking exist in the compiler but are untested; video-scene and user-upload visuals are untested; no web UI for creating a video yet (API only); transcription tool endpoint and SRT/VTT export; Piper voices; voices table seed (35+ voices incl. Nigerian English is not possible with Kokoro alone); chunked uploads; Excel layer.
Next: Phase 4 builds the six styles, the standalone tools and Auto Clipping on this pipeline.

### Phase 4 report (2026-11-06)

Built: resumable chunked uploads (size/quota caps per plan, ffprobe validation, metadata stripped, ownership checks) + media library; renderer extended (split-screen layout, ranking badges, on-screen text, source-clip audio ducked under the voice, music sidechain ducking); five style builders (Text Story, Video Story, Ranking, Split Screen, Commentary) behind one `/render/create` job with plan gating and credit reserve/settle/refund; user errors fail fast without retries; local transcription with SRT/VTT/TXT export and word editing; Auto Clipping (sentence-snapped windows, heuristic pre-filter, batched AI scoring with an honestly labelled heuristic fallback, OpenCV face tracking with smoothed crop path, blur and centre fallbacks, burned captions, loudness, previews); tools: ideas, title scorer, script enhancer, thumbnails (Pillow, 4 layouts, 1280x720), voiceover (MP3), cached voice previews; web UI for all of it (dashboard, create forms with live cost preview, tools hub and panels, media library, videos list), mobile bottom nav.
Verified by running: 61 pytest tests green (upload resume/duplicate chunk/rejections/metadata stripping, every style end to end through the real worker and renderer with a fake TTS, plan gating, music ducking, ownership isolation, credits on success/failure/cancel, transcript edit/download, clipping windows and picking, injection-in-transcript, thumbnails, voiceover); Playwright e2e on real Chrome with real Kokoro, Whisper and FFmpeg: signup through the UI, Text Story render and playback (1080x1920), Ranking on a 360x640 touch viewport, thumbnails (4 real PNGs at 1280px), Auto Clipping upload -> analyse -> export (1080x1920), every creation form with no sideways scroll at 360 and 1280. Real runs: 78 s speech file transcribed by Whisper tiny in 20 s; face tracking followed a moving face (38 of 40 samples, path 0.29 -> 0.45); frames inspected.
Bugs found by running and fixed: broken logo image everywhere (the copy of icon.svg into public/ was lost in a failed shell batch in Phase 1; marketing pages affected since then, now asserted in e2e); OpenCV 5 has no Haar cascade (pinned to 4.x); face detector needed higher resolution; relative source path broke ffmpeg's cwd; SSE through Chrome's gzip was buffered by Next's proxy (added no-transform) and streams can stall, so the client now self-heals with a 6 s heartbeat poll; credit guard raised outside its try block.
NOT verified: any LLM-backed path against a real OpenRouter key (ideas, title scorer, enhancer, planner, AI clip scoring all tested with fake providers only); Video Story with AI/Wikimedia images through the UI (provider calls were tested live in Phase 3, the style itself with procedural visuals); Commentary and Split Screen through the browser (API/worker only); Whisper `small` default (tests used `tiny`; `small` downloads ~480 MB and is slower); a 10-minute source (tested 78 s; transcription speed was about 4x real time on this CPU, so 10 min is roughly 2.5 min); video generation plugins; client-side 720p compression before upload; captions styles beyond the one highlight look; the Piper voice plugin; Nigerian English voices (Kokoro has none).
Limits to know: free-plan upload cap 200 MB; the e2e suite needs the models and a running stack, so CI runs backend tests and type-checks only.
