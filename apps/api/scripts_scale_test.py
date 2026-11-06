"""Scale check: a ~10 minute source through the real Whisper model, clip scoring and a face-tracked export.

The source is the 78 s sample repeated, so the *text* repeats, but length, memory and timing are real.
Run from apps/api (after generating storage/sample/talk.mp4):  python scripts_scale_test.py [whisper-size]
"""
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
size = sys.argv[1] if len(sys.argv) > 1 else "small"
os.environ["WHISPER_MODEL"] = size

from clue.ai.clipping import score_windows  # noqa: E402
from clue.ai.transcribe import transcribe  # noqa: E402
from clue.core.db import SessionLocal  # noqa: E402
from clue.core.media import duration, run_ffmpeg  # noqa: E402
from clue.render.reframe import export_clip  # noqa: E402

sample = Path("../../storage/sample")
src, long_ = sample / "talk.mp4", sample / "long10.mp4"
if not long_.exists():
    (sample / "long.txt").write_text("".join(f"file '{src.name}'\n" for _ in range(8)))
    run_ffmpeg(["-f", "concat", "-safe", "0", "-i", str((sample / "long.txt").resolve()), "-c", "copy", str(long_.resolve())])
print(f"source: {duration(long_) / 60:.1f} minutes, {long_.stat().st_size / 1e6:.0f} MB", flush=True)

t = time.time()
last = [0]
tr = transcribe(long_, size=size, on_progress=lambda p: (print(f"  transcribing {p}%", flush=True) if p - last[0] >= 20 else None, last.__setitem__(0, p) if p - last[0] >= 20 else None))
dt = time.time() - t
print(f"whisper '{size}': {dt:.0f} s for {duration(long_):.0f} s of audio ({duration(long_) / dt:.2f}x real time), {len(tr['words'])} words, language {tr['language']}", flush=True)

t = time.time()
with SessionLocal() as db:
    rows, scorer = score_windows(db, tr["words"], 8, None)
print(f"scoring ({scorer}): {len(rows)} clips in {time.time() - t:.1f} s", flush=True)
for r in rows[:4]:
    print(f"  {r['score']:3d}  {r['start']:6.1f}-{r['end']:6.1f}  {r['title']!r}")

t = time.time()
out = sample / "long_clip.mp4"
info = export_clip(long_, rows[0]["start"], rows[0]["end"], out, tr["words"], mode="face")
print(f"export (mode used: {info['mode']}): {time.time() - t:.0f} s, {out.stat().st_size / 1e6:.1f} MB", flush=True)
print("DONE")
