# Costs

Status: **measured so far on one machine only** (Windows 10, Intel i5-6300U, 4 threads, no GPU). No LLM cost has been measured yet because no OpenRouter key has been used.

## Running cost per service

| Service | Free limit | What happens at the limit |
|---|---|---|
| OpenRouter free models | About 20 requests/min, 50/day on an account that never bought credits (reported by OpenRouter; re-check) | Clear message; non-AI features keep working; one request per video; responses cached by content hash |
| Kokoro TTS (local) | None | n/a. CPU only |
| faster-whisper (local) | None | n/a. CPU only |
| FFmpeg (local) | None | n/a |
| Pollinations images | Slow and rate-limited anonymous tier | Best effort, cached; renders fall back to procedural backgrounds |
| Wikimedia Commons | Public API with fair use | Cached; skips on failure |
| Hosting | Your own computer | n/a |

## Measured render times (this laptop)

| Task | Result |
|---|---|
| Kokoro synthesis, first call incl. model load | about 23 s for a 3.6 s sentence; later scenes are faster |
| Whisper `tiny` word alignment of one scene | about 4-8 s |
| Real 12.3 s video, 2 scenes, voice + alignment + render | 65 s end to end |
| Real 8.6 s video through the API | completed, 837 KB file |
| Golden render test (2 scenes, 3.9 s) | about 4 s |
| Whisper `tiny` transcription of 78 s of speech | about 20 s (about 4x real time) |
| Face sampling over a 30 s clip (40 samples at 1280 px) | about 15 s |
| Face-tracked, captioned export of a 30 s clip to 1080x1920 | about 35 s |
| Real Text Story (3 sentences, 8 s video), end to end in the UI | about 47 s including Kokoro load |

| Whisper `small` on a 10.4-minute source | 460 s (1.35x real time) on the i5-6300U; plugged in |
| Re-voicing one scene with Kokoro | a few seconds |
| Cinematic render of a short edited video, end to end in the editor | about 1 minute (laptop on charger) |

Rule of thumb on this hardware: rendering takes roughly 5x the video length. A 60-second Short should take a few minutes. A server with more cores will be faster.

## Cost per video and margin per plan (a model built on the measurements above)

**What is measured and what is not.** Render time is measured (above). The price of the server, the exchange rate, the payment fee and the AI token counts are **assumptions**, written out so you can change them. No OpenRouter key has been used yet, so AI cost per video is **estimated, not measured**. After your first real videos, the Admin dashboard shows the true AI cost per finished video (Admin > Overview, `AI cost ... per finished video`); replace the estimate with that number.

Assumptions (edit these):

| Item | Value | Source |
|---|---|---|
| Server | 4 vCPU VPS, about $30 per month | typical price, not a quote |
| Exchange rate | N1,500 per $1 | assumption, check today's rate |
| Server speed vs. the test laptop | 2x faster | assumption; the laptop is a 2015-era 2-core i5 |
| Fast video (about 45 s) render time on the laptop | about 225 s (5x length, measured rule of thumb) | measured |
| Pro / Cinematic render time | 1.6x / 3x of Fast | Cinematic about 1 minute for a short edit; ratio estimated |
| Average server busy time | 30% | assumption |
| AI per video (planner, one call) | about 3,000 tokens in, 1,500 out | estimated from the prompt size |
| AI price | free models: N0; if you pay: about $0.50 per million in, $1.50 per million out | assumption |
| Payment fee | 1.5% + N100 per charge | typical Nigerian card gateway; check yours |

Derived per-video cost:

| | Compute | AI (paid model) | AI (free model) | Total (paid AI) |
|---|---|---|---|---|
| Fast (5 credits) | about N6 | about N6 | N0 | about N12 |
| Pro (8 credits) | about N10 | about N6 | N0 | about N16 |
| Cinematic (14 credits) | about N19 | about N6 | N0 | about N25 |

(Compute: $30 x 1,500 = N45,000 per month; 2.6 million seconds per month x 30% busy = 777,600 usable seconds; a Fast video needs about 112 s on the faster server = 6,900 videos = about N6.5 each.)

Margin per plan, worst case (the customer spends every credit on the most expensive mode they can use), monthly plan, paid AI, before fixed costs:

| Plan | Price | Credits | Worst-case videos | Cost of those videos | Payment fee | Gross margin |
|---|---|---|---|---|---|---|
| Starter | N9,900 | 200 | 40 Fast | N480 | N249 | about 93% |
| Creator | N19,900 | 500 | 35 Cinematic | N875 | N399 | about 94% |
| Business | N49,900 | 1,200 | 85 Cinematic | N2,125 | N849 | about 94% |

One credit is worth about N50 (Starter) and a Fast video costs the customer N250 in credits against about N12 of cost to you. The numbers that actually hurt are **fixed**: the server (about N45,000 per month) and your time. At these prices you break even on the server with about 5 Starter subscribers. Top-up packs cost more per credit than plans (N60 per credit at the 100 pack), so they never undercut subscriptions.

Things that would make these numbers wrong: a slower or busier server (a queue builds up and renders get slow), free models running out so you must pay for AI, refunds (see `docs/LICENSES.md` and the refund policy page), card chargebacks, and Whisper `small` for long-video Auto Clipping, which is far heavier than a Fast video (about 1.35x real time on the laptop; a 10-minute source takes about 7 minutes of laptop time and that is charged as 8 + 2 per clip credits, so check it against your real server speed before selling it).
