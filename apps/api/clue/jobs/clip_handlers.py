"""Job handlers for transcription and Auto Clipping."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from clue.core import credits, storage
from clue.jobs import queue, styles
from clue.jobs.registry import handler
from clue.models import Asset, Clip, Job, Transcript


def _settle(db: Session, job: Job) -> None:
    if job.credit_ref and job.user_id:
        credits.settle(db, job.user_id, job.credit_ref)


def _own_asset(db: Session, job: Job, asset_id: str, kinds: tuple[str, ...]) -> Asset:
    a = db.get(Asset, asset_id)
    if a is None or a.user_id != job.user_id or a.kind not in kinds:
        raise styles.SpecError("That media file was not found. Pick it again from your library.")
    return a


def _transcribe_asset(db: Session, job: Job, a: Asset, language: str | None, lo: int, hi: int) -> Transcript:
    from clue.ai import transcribe as tr

    res = tr.transcribe(storage.safe_path(a.path), language=language,
                        on_progress=lambda p: queue.progress(db, job.id, lo + (hi - lo) * p // 100, "transcribing"))
    if not res["words"]:
        raise styles.SpecError("No speech was found in this file.")
    for old in db.scalars(select(Transcript).where(Transcript.asset_id == a.id)).all():
        db.delete(old)
    t = Transcript(user_id=a.user_id, asset_id=a.id, language=res["language"], words=res["words"], segments=res["segments"])
    db.add(t)
    db.commit()
    return t


@handler("transcribe")
def transcribe_job(db: Session, job: Job) -> dict:
    a = _own_asset(db, job, job.payload["asset_id"], ("video", "audio"))
    t = _transcribe_asset(db, job, a, job.payload.get("language"), 5, 95)
    _settle(db, job)
    return {"transcript_id": t.id, "words": len(t.words), "language": t.language}


@handler("autoclip_analyze")
def autoclip_analyze(db: Session, job: Job) -> dict:
    from clue.ai.clipping import score_windows
    from clue.render.reframe import thumbnail

    a = _own_asset(db, job, job.payload["asset_id"], ("video",))
    n = int(job.payload.get("n", 8))
    t = db.scalar(select(Transcript).where(Transcript.asset_id == a.id).order_by(Transcript.id.desc()))
    if t is None:
        t = _transcribe_asset(db, job, a, job.payload.get("language"), 5, 65)
    queue.progress(db, job.id, 68, "finding the best moments")
    rows, scorer = score_windows(db, t.words, n, job.user_id)
    if not rows:
        raise styles.SpecError("No clip-length moments were found. Clips need 15 to 60 seconds of continuous speech.")
    for old in db.scalars(select(Clip).where(Clip.asset_id == a.id)).all():
        db.delete(old)
    db.commit()
    ids = []
    for i, r in enumerate(rows):
        queue.progress(db, job.id, 80 + int(18 * i / len(rows)), "making previews")
        c = Clip(user_id=a.user_id, asset_id=a.id, transcript_id=t.id, scorer=scorer, **r)
        db.add(c)
        db.commit()
        try:
            thumbnail(storage.safe_path(a.path), r["start"] + min(1.0, (r["end"] - r["start"]) / 4), storage.root() / f"{a.user_id}/clips/{c.id}.jpg")
        except Exception:  # noqa: BLE001  (a missing preview must not fail the analysis)
            pass
        ids.append(c.id)
    _settle(db, job)
    return {"clips": ids, "scorer": scorer}


@handler("autoclip_export")
def autoclip_export(db: Session, job: Job) -> dict:
    from clue.render.reframe import export_clip

    p = job.payload
    c = db.get(Clip, p["clip_id"])
    if c is None or c.user_id != job.user_id:
        raise styles.SpecError("That clip was not found. Run the analysis again.")
    a = db.get(Asset, c.asset_id)
    t = db.get(Transcript, c.transcript_id)
    rel = f"{c.user_id}/clips/{c.id}.mp4"
    queue.progress(db, job.id, 10, "reframing")
    info = export_clip(storage.safe_path(a.path), c.start, c.end, storage.root() / rel, t.words, mode=p.get("reframe", "face"),
                       captions=bool(p.get("captions", True)), watermark=p.get("watermark"))
    c.output_path = rel
    db.commit()
    _settle(db, job)
    return {"output": rel, "clip_id": c.id, **info}


@handler("voiceover")
def voiceover_job(db: Session, job: Job) -> dict:
    """Standalone TTS tool: text to an MP3 (scene by scene so long text never hits engine limits)."""
    from clue.ai.tts import get_tts
    from clue.core.media import run_ffmpeg
    from clue.jobs.text_story import split_scenes

    p = job.payload
    parts = split_scenes(p["text"])
    if not parts:
        raise styles.SpecError("Please enter some text.")
    tts, d = get_tts(), storage.user_dir(job.user_id, f"jobs/{job.id}")
    wavs = []
    for i, part in enumerate(parts):
        queue.progress(db, job.id, 5 + int(85 * i / len(parts)), f"voice {i + 1}/{len(parts)}")
        w = d / f"v{i:03d}.wav"
        tts.synthesize(part, p.get("voice", "af_heart"), float(p.get("speed", 1.0)), w)
        wavs.append(w)
    (d / "list.txt").write_text("\n".join(f"file '{w.name}'" for w in wavs) + "\n", encoding="utf-8")
    rel = f"{job.user_id}/outputs/{job.id}.mp3"
    out = storage.root() / rel
    out.parent.mkdir(parents=True, exist_ok=True)
    run_ffmpeg(["-f", "concat", "-safe", "0", "-i", "list.txt", "-c:a", "libmp3lame", "-q:a", "3", str(out)], cwd=d)
    _settle(db, job)
    return {"output": rel}
