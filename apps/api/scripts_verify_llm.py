"""Live check of every LLM-backed feature against a REAL model.

Usage (from apps/api):  python scripts_verify_llm.py
Needs your OpenRouter key saved at /setup (or OPENROUTER_API_KEY in .env). Uses your real database and counts toward your free quota (about 5 requests).
Prints what came back, token use and any schema failures. Nothing here is mocked.
"""
import json
import sys
import time

from clue.ai import clipping
from clue.ai.llm import LLMError, get_provider
from clue.ai.prompts import tools as T
from clue.ai.prompts.plan import plan_video
from clue.core.db import SessionLocal
from clue.models import ApiUsage

WORDS = []
t = 0.0
SENT = ["Here is the biggest mistake new creators make.", "They spend ten hours editing a video nobody asked for.", "Stop doing that today.",
        "Instead, start with the question your viewer is already asking.", "If you can answer it in three seconds, they will stay.",
        "If you cannot, they swipe, and no editing trick will save you.", "Let me tell you a story about a friend who posted twenty videos.",
        "Nineteen of them flopped, but one reached half a million people.", "Do you know what that one had in common with the others?", "Nothing at all."]
for s in SENT:
    for w in s.split():
        WORDS.append({"w": w, "start": round(t, 2), "end": round(t + 0.42, 2)})
        t += 0.45
    t += 0.4


def main() -> int:
    fails = 0
    with SessionLocal() as db:
        print("provider:", get_provider(db).name)
        checks = {
            "plan_video": lambda: plan_video(db, "A man comes home and the kettle is still warm", style="text_story", tone="nigerian_english", seconds=30),
            "ideas": lambda: T.ideas(db, "football in Lagos", "young fans"),
            "score_title": lambda: T.score_title(db, "How I edit shorts"),
            "enhance_script": lambda: T.enhance_script(db, "So today I want to talk about something. It is about saving money. Many people do not save.", "hook", 20),
            "clip_scoring": lambda: clipping.score_windows(db, WORDS, 2, None),
        }
        for name, fn in checks.items():
            t0 = time.time()
            try:
                out = fn()
                body = out if isinstance(out, tuple) else out.model_dump()
                print(f"\n[OK]  {name} ({time.time() - t0:.1f}s)\n", json.dumps(body, indent=1, default=str)[:700])
                if name == "clip_scoring" and out[1] != "ai":
                    print("      WARNING: scorer fell back to heuristic, AI scoring did not succeed"); fails += 1
            except (LLMError, Exception) as e:  # noqa: BLE001
                fails += 1
                print(f"\n[FAIL] {name}: {e.__class__.__name__}: {e}")
        used = db.query(ApiUsage).count()
        print(f"\napi_usage rows logged: {used}; failures: {fails}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
