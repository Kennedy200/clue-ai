"""Clue Score: a fast, local, explainable 0-100 score for a short-video script (no AI key, no credits).

Five parts: hook 30, pacing 25, clarity 20, specificity 15, call to action 10. Every lost point maps to a tip.
"""
from __future__ import annotations

import re

WORDS_PER_SEC = 2.5
WEAK_OPENERS = ("hi", "hello", "hey guys", "welcome", "in this video", "today i", "today we", "so ", "um", "good morning")
HOOK_WORDS = {"stop", "never", "mistake", "secret", "why", "how", "truth", "nobody", "wrong", "before", "without", "worst", "best", "free", "fast", "now", "you", "your", "imagine"}
FILLERS = {"basically", "literally", "very", "really", "just", "actually", "totally", "kind", "sort", "stuff", "things", "maybe", "probably"}
CTA_WORDS = ("follow", "subscribe", "comment", "share", "save", "tell me", "link in", "try it", "send this", "tag a", "let me know", "check out", "download", "sign up")
POWER = {"free", "proven", "secret", "mistake", "easy", "fast", "instantly", "simple", "powerful", "surprising", "shocking", "hidden", "exact", "step", "money", "save", "grow", "win"}


def _sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+|\n+", text.strip())
    return [p.strip() for p in parts if len(p.split()) >= 1]


def _words(text: str) -> list[str]:
    return re.findall(r"[A-Za-z0-9']+", text.lower())


def score_script(script: str, seconds: int | None = None) -> dict:
    sents = _sentences(script)
    words = _words(script)
    if len(words) < 5:
        return {"score": 0, "parts": {}, "tips": ["Write at least a couple of sentences to get a score."], "words": len(words), "grade": "-"}
    tips: list[str] = []
    first = sents[0]
    fw = _words(first)

    # hook (30)
    hook = 0
    if len(fw) <= 14:
        hook += 10
    else:
        tips.append(f"Your first line is {len(fw)} words. Cut it to 14 or fewer so it lands in two seconds.")
    if "?" in first or any(c.isdigit() for c in first):
        hook += 7
    else:
        tips.append("Open with a question or a number to create curiosity.")
    hits = len(set(fw) & HOOK_WORDS)
    hook += min(8, hits * 4)
    if hits == 0:
        tips.append("Speak to the viewer: words like 'you', 'stop', 'never' or 'why' make a first line stick.")
    if any(first.lower().startswith(w) for w in WEAK_OPENERS):
        hook = max(0, hook - 10)
        tips.append("Skip greetings and 'in this video'. Start with the most interesting thing.")
    else:
        hook += 5

    # pacing (25)
    lens = [len(_words(s)) for s in sents]
    avg = sum(lens) / len(lens)
    pace = 0
    if 6 <= avg <= 16:
        pace += 12
    else:
        tips.append("Aim for sentences of 6 to 16 words on average." + (" Yours run long." if avg > 16 else " Yours are choppy."))
        pace += 5
    spread = max(lens) - min(lens)
    if len(lens) >= 3 and spread >= 4:
        pace += 6
    elif len(lens) >= 3:
        tips.append("Mix short and long sentences so the voice has rhythm.")
    else:
        pace += 3
    if seconds:
        target = seconds * WORDS_PER_SEC
        ratio = len(words) / target
        if 0.8 <= ratio <= 1.15:
            pace += 7
        else:
            tips.append(f"For {seconds} seconds you want about {int(target)} words; you have {len(words)}.")
    else:
        pace += 4 if len(words) <= 160 else 0
        if len(words) > 160:
            tips.append("Over 160 words is more than a minute of speech. Consider splitting it into two videos.")

    # clarity (20)
    avg_len = sum(len(w) for w in words) / len(words)
    fill = sum(1 for w in words if w in FILLERS)
    clarity = 20
    if avg_len > 5.2:
        clarity -= 6
        tips.append("Use shorter, everyday words. Your average word is long.")
    if fill:
        clarity -= min(10, fill * 3)
        tips.append(f"Remove filler words ({', '.join(sorted({w for w in words if w in FILLERS}))}).")
    if any(n > 28 for n in lens):
        clarity -= 4
        tips.append("One sentence runs past 28 words. Split it.")

    # specificity (15)
    spec = 0
    digits = sum(1 for w in words if any(c.isdigit() for c in w))
    spec += min(8, digits * 4)
    if digits == 0:
        tips.append("Add one concrete number, name or example to make it believable.")
    spec += min(7, len(set(words) & POWER) * 3)

    # call to action (10)
    last = " ".join(sents[-2:]).lower()
    cta = 10 if any(c in last for c in CTA_WORDS) else 0
    if not cta:
        tips.append("End with one clear action: follow, comment, save or share.")

    parts = {"hook": min(30, hook), "pacing": min(25, pace), "clarity": max(0, clarity), "specificity": min(15, spec), "cta": cta}
    total = sum(parts.values())
    grade = "A" if total >= 85 else "B" if total >= 70 else "C" if total >= 55 else "D" if total >= 40 else "E"
    return {"score": total, "parts": parts, "max": {"hook": 30, "pacing": 25, "clarity": 20, "specificity": 15, "cta": 10},
            "tips": tips[:6], "words": len(words), "est_seconds": round(len(words) / WORDS_PER_SEC), "grade": grade}


def template_hooks(script: str) -> list[str]:
    """Keyless fallback for 'Fix my hook': honest templates around the script's own key phrase."""
    first = _sentences(script)[0] if _sentences(script) else script
    words = [w for w in _words(first) if len(w) > 3 and w not in FILLERS and w not in {"this", "that", "with", "have", "from", "your", "what", "when", "they", "about", "into", "video"}]
    topic = " ".join(words[:3]) or "this"
    return [
        f"Stop doing {topic} the hard way.",
        f"Why does nobody talk about {topic}?",
        f"The biggest mistake with {topic}, and the fix in 30 seconds.",
    ]
