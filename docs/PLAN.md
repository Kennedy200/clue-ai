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
- [x] **Phase 4 – Styles + tools** (built and e2e-tested; AI-dependent paths still unverified against OpenRouter, see Phase 5 report): 6 styles, standalone tools, Auto Clipping.
- [x] **Phase 5 – Editor**: preview, timeline, panels, captions, autosave, mobile layout, Pro/Cinematic.
- [x] **Phase 6 – Money**: ledger, plans, internal billing, invoices, referrals, Clue Score + Clue Card.
- [x] **Phase 7 – Teams, brand kits, bulk, YouTube publish, analytics, admin, xlsx.**
- [x] **Phase 8 – Hardening**: security, perf, a11y, backups, runbook, COSTS with measured numbers, e2e.

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

### Phase 5 report + gap closure (2026-11-06)

**Editor built:** project load/save API with conflict-safe versions (409 on a stale tab), 30-step history with restore, path ownership checks (a project can only reference the user's own files or the shared public image cache), per-scene and whole-video re-voice, free-photo / AI-image search with import (host allow-list against SSRF, author + licence kept), 480p proxy videos for the preview, re-render with plan gating and credit refund on failure that never leaves the editor locked. Web: in-browser preview that plays the same Scene JSON (visuals, voice, captions, badges, split layout), timeline (select, drag to reorder, trim handle, keyboard), panels for Scene / Captions (10 presets + colours, size, position, word fixes) / Voice / Music / Export, undo/redo with edit merging, autosave with offline draft kept on the device and retried, shortcuts (Space, Ctrl+Z/Y/S, arrows, D, Delete), phone layout with a collapsible bottom sheet. Renderer: 10 caption styles incl. boxes, uppercase and Pro/Cinematic "pop" animation; fade transitions; Cinematic colour grade, vignette and film grain; music sidechain ducking (now tested).

**Gap closure from earlier phases:**
- Browser coverage: Split Screen, Commentary (with ducked source sound editable in the editor), Video Story with live Wikimedia photos, editor photo swap, Auto Clipping, thumbnails: all pass in real Chrome.
- Whisper `small` (the default) downloaded and run on a 10.4-minute source (the 78 s sample repeated 8 times, so the text repeats): 460 s, 1.35x real time on this CPU, 1,800 words, face-tracked export worked.
- Client-side 720p "Save data": built (MediaRecorder, real time), skips files whose bitrate is already low, never makes a file bigger; e2e: a 20 MB 1080p file became a 720p WebM at under half the size with audio. Defaults on only when the browser reports Data Saver or a slow connection.
- Extra caption styles: 10 presets (spec asked 8+).
- Local voices: Piper plugin with 11 voices (UK/US English, French, Spanish, Portuguese, Arabic, Swahili), real model run and speed change verified. Nigerian English: `edge-tts` plugin (en-NG-AbeoNeural, en-NG-EzinneNeural, plus Kenyan/South African), live synthesis verified; **online only, unofficial client, not for commercial products**. No local Nigerian voice exists in Kokoro or Piper. Both plugins are off by default with an admin toggle (UI + e2e).
- LLM paths: **still not verified against OpenRouter** (no key on this machine). I tried a keyless real model (Pollinations text): it now answers 401, so I removed that provider rather than ship a broken option. `npm run verify:llm` runs plan, ideas, title score, enhance and AI clip scoring against your real key (about 5 requests) and reports failures; run it after saving your key at /setup.

**Bugs found by running it and fixed (this round):** ASS ``/`	` escapes were being written as control characters; captions did not wrap (WrapStyle 2) and overflowed; Wikimedia thumbnails come from `thumb.wikimedia.org` which my SSRF allow-list blocked; the file-signing endpoint rejected the shared image cache; Piper re-downloaded voices on every start; browser-recorded WebM had no duration; admin plugin toggle waited for the server (now optimistic); phone bottom sheet hid the timeline (now starts collapsed); a half-applied migration left my dev DB inconsistent (fresh installs verified by a new test: migrations from nothing equal the models, no drift).

**Not done / limits:** Cinematic light-leak transitions and SFX hits are not built; no built-in music library (your own uploads only) and the preview does not play music (the render does); the preview is a DOM approximation of the FFmpeg render (fonts, wrapping and zoom easing can differ slightly); proxies exist only for uploaded videos; brand-kit panel arrives with Phase 7; shrinking needs a foreground tab (browsers throttle hidden tabs) and Chrome-family MediaRecorder; Whisper `small` needs about 7.7 minutes for a 10-minute video on this CPU.
**Tests:** 81 backend, 11 web unit (scene ops, undo/redo, merging, conflict, offline retry), 20 Playwright e2e files/tests on real Chrome (desktop 1280 and phone 360 touch).

### Phase 6 report (2026-11-06)

**Built:** `core/billing.py` internal billing engine (simulated gateway, `Gateway` is the swap point for a real-gateway plugin). Subscribe monthly or yearly (yearly = 6x monthly = 50% off, 12 months of credits granted up front), NGN or USD. Upgrades are charged now minus the unused part of the current period; downgrades and cancels apply at period end (user keeps plan and credits until then). Failed renewals retry after 1, 3 and 5 days with dev-mail notices, then the account drops to Free. One-off top-up packs (100/300/1000) with an idempotency key so a double click cannot charge twice. Numbered invoices (`CLUE-YYYY-NNNNNN`, failed attempts recorded too), printable invoice page, receipt emails to the dev inbox, credit history from the append-only ledger. The worker runs renewals every 5 minutes. Referral link prefills signup; both sides get 10 credits (saas mode only). **Clue Score**: local, explainable 0-100 (hook 30, pacing 25, clarity 20, specifics 15, CTA 10) with tips, free, no key. **Fix my hook**: AI rewrite (1 credit) when a key exists, otherwise free templates; a failed AI attempt is refunded. **Clue Card**: 1080x1350 PNG with score ring, bars and your invite link.

**Verified:** 95 backend tests (14 new: proration, annual price, downgrade at period end, cancel then free, declined card changes nothing, retry schedule and drop to Free, idempotent top-up, ledger sums, referral both sides, invoice ownership, score ordering, card is a 1080x1350 PNG); Playwright on desktop and 360 px phone: upgrade, top-up, invoice page, cancel, referral prefill, score, fix hook, card download.

**Not verified / limits:** no real payment gateway (nothing here moves money; the pricing and billing pages say so). AI "Fix my hook" path untested against OpenRouter. Subscription periods are 30/365 days, not calendar months. The Clue Score is a heuristic, not a prediction of views. Referral rewards are not yet held back until the friend verifies their email (abuse risk, to harden in Phase 8). Currency conversion is fixed prices per currency, not live rates.

### Phase 7 report (2026-11-06)

**Built:** Teams with four roles (owner, admin, editor, viewer; max 10 people incl. pending invites; email invites that only the invited address can accept, single use, 7 days; non-members get a 404 so team ids are not revealed). Teams share finished videos (read and download) and brand kits; they do **not** co-edit one project (each video stays in its owner's account, so file ownership checks stay simple and safe). Brand kits (caption look, closing line) personal or team-wide, applied in the editor's Captions tab or to a whole bulk batch. Bulk CSV: up to 25 text-story videos, comma/semicolon/tab, all rows validated first, total credits checked first, so a bad row or low balance charges nothing. Content calendar with a "publish pack" (title, description, hashtags, download) that works for every platform. Optional YouTube upload (OAuth + resumable upload as a background job, tokens encrypted per user). Personal analytics (videos, minutes, credits per day, by style). Admin panel: dashboard (users, revenue, jobs, AI cost per feature and per finished video), user search, credit adjustments with reason, plan change, suspend, plan editing, audit log, OpenRouter and YouTube settings. Excel: one export workbook (Plans, Users, Invoices, Ledger, LlmUsage, CreditGrants), import of Plans and CreditGrants with a dry run first and all-or-nothing apply; cells starting with = + - @ are neutralised on export.

**Bugs found by running it:** the Business plan lacked the brand_kit flag (existing databases now get new feature flags merged in without overwriting admin edits); calendar times were converted to the server's local zone instead of UTC; the invite link `?ref=` was fine but dates were shown in the wrong zone until fixed.

**Verified:** 12 new backend tests (roles and permission edges, plan gates, brand kit ownership, bulk atomicity, calendar ownership, publish pack, analytics, YouTube OAuth + upload against a mocked Google, admin permissions, dashboard numbers, xlsx export/injection, xlsx import dry-run/apply/rollback); Playwright on desktop and 360 px phone: invite and join as a second browser user, brand kit, bulk with a bad row blocked then success, calendar, analytics, admin credits and audit.

**NOT verified / limits:** YouTube upload has never run against real Google (no OAuth client here; tested against a mock only), so expect first-contact fixes (consent screen verification, quota). Teams do not co-edit. No per-seat billing. Team pricing is the Business plan only. The calendar reminds nothing (no push or email reminders), it is a planner. Fonts in brand kits depend on the fonts installed where FFmpeg renders. Analytics cover this app's data only, not views from platforms. Bulk is text stories only (not other styles). The signup rate limit (5 per minute per IP) can make rapid multi-user e2e runs flaky.

### Phase 8 report (2026-11-07)

**Security review (found by reading the code, fixed, each with a test):** anyone could become admin on a hosted install by signing up with `ADMIN_EMAIL` before verifying it; referral credits were paid before the friend verified an email (farmable) and had no cap; changing a password left other devices signed in; behind a proxy every visitor shared one rate-limit bucket (the whole site would lock after 5 signups a minute); no security headers or body-size limits. Added: CSP and friends in Next, an ASGI guard in the API (no SSE buffering), proxy-aware client IP. Dependencies: `pip-audit` clean after upgrading FastAPI/Starlette (0.41 -> 1.10), cryptography, python-multipart, pytest, and pinning the unpinned packages; the unused `zod` was removed; `npm audit` still reports PostCSS inside Next 15 (build-time, not user-reachable).

**Also built:** real SMTP sending (env-configured, never breaks a request; before this a hosted install had no way to deliver verification mail), backup/restore tool (`python -m clue.backup`, consistent while running, checksums, secret included, refuses damaged or unsafe archives, never deletes existing data), credits-ledger reconciliation (finds credits held by crashed jobs, admin can return them, audit-logged), animated Clue Score (CSS only), Docker + Caddy deployment files, RUNBOOK, SECURITY checklist, measured/modelled COSTS with margin per plan in naira.

**Verified:** 124 backend tests (Starlette 1.x included), 11 web unit tests, Playwright full run (26 passed, 3 failed, 19 skipped by design): 2 failures were load (one worker, 25-minute run; both pass alone in 31 s and 12 s) and 1 was a real contrast bug in the brand-kit preview (fixed, passes). WCAG 2.1 A/AA via axe on 14 public and 14 signed-in pages: clean, with zero console errors under the CSP. Backup + verify + restore on the real dev database while the app was running: table counts and ledger sum identical.

**Lighthouse (production build, mobile, median of 3, slow laptop under load):** Home 87, Pricing 87 (best runs 92 and 89); accessibility 100; best practices 100; LCP 0.8 s. Not at the 90 target: remaining cost is Next/React hydration (about 700 ms scripting at 4x CPU throttle), not our code. Re-measure on a faster machine or after hosting with HTTP/2 and brotli.

**NOT verified / not done:** AI features against a real OpenRouter key; YouTube against real Google; the Docker files were never run; SMTP only against a mock; restore only rehearsed on this machine; payments simulated; Lighthouse 90; no external pen test; no 2FA; Redis-backed rate limit; Cinematic light leaks and SFX; built-in music library; GitHub repo not created (needs `gh`).
