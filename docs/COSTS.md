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

Rule of thumb on this hardware: rendering takes roughly 5x the video length. A 60-second Short should take a few minutes. A server with more cores will be faster.

## Margin per plan

Not yet computed. It needs measured LLM tokens per video (`api_usage` table) and a hosting choice. Do not quote prices to customers from this file yet.
