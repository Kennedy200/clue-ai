"""Job handlers registered with the worker."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from clue.core import credits, storage
from clue.core.db import SessionLocal
from clue.jobs import queue
from clue.jobs import styles
from clue.jobs.text_story import build_project, output_path
from clue.models import Asset, Job, Project
from clue.core.media import MediaError
from clue.render.compiler import RenderCancelled, render
from clue.render.scene import CaptionStyle, SceneProject
from clue.jobs.registry import handler


def _settle(db: Session, job: Job) -> None:
    if job.credit_ref and job.user_id:
        credits.settle(db, job.user_id, job.credit_ref)


def _cancelled(job_id: str):
    def check() -> bool:
        with SessionLocal() as s:
            j = s.get(Job, job_id)
            return j is None or j.status == "cancelled"
    return check


def _render_and_save(db: Session, job: Job, project: SceneProject, proj: Project, rel_prog_base: int = 0) -> dict:
    out, rel = output_path(job.user_id, job.id)
    try:
        info = render(project, out, on_progress=lambda p, s: queue.progress(db, job.id, p, s), cancelled=_cancelled(job.id))
    except RenderCancelled:
        proj.status = "failed"
        db.commit()
        return {"cancelled": True}
    proj.scene_json = project.model_dump()
    proj.output_path = rel
    proj.duration = int(info["duration"] * 1000)
    proj.status = "done"
    db.commit()
    if job.credit_ref:
        credits.settle(db, job.user_id, job.credit_ref)
    return {"output": rel, "project_id": proj.id, **info}


@handler("render_text_story")
def render_text_story(db: Session, job: Job) -> dict:
    p = job.payload
    proj = db.get(Project, p["project_id"])
    proj.status = "rendering"
    db.commit()
    project = build_project(
        job.user_id, job.id, p["text"], p.get("voice", "af_heart"), float(p.get("speed", 1.0)), int(p.get("seed", 0)),
        CaptionStyle(**p.get("caption", {})), p.get("watermark"), p.get("mode", "fast"),
        on_progress=lambda pct, stage: queue.progress(db, job.id, pct, stage),
    )
    return _render_and_save(db, job, project, proj)


@handler("render_video")
def render_video(db: Session, job: Job) -> dict:
    p = job.payload
    proj = db.get(Project, p["project_id"])
    proj.status = "rendering"
    db.commit()
    try:
        project = styles.build(
            db, job.user_id, job.id, p["style"], p["spec"], voice=p.get("voice", "af_heart"), speed=float(p.get("speed", 1.0)),
            seed=int(p.get("seed", 0)), caption=CaptionStyle(**p.get("caption", {})), watermark=p.get("watermark"), mode=p.get("mode", "fast"),
            music_asset_id=p.get("music_asset_id"), on_progress=lambda pct, stage: queue.progress(db, job.id, pct, stage),
        )
        return _render_and_save(db, job, project, proj)
    except MediaError as e:  # e.g. over the mode's length cap: the user must shorten the script, retrying will not help
        raise styles.SpecError(str(e)) from e
    except Exception:
        proj.status = "failed"
        db.commit()
        raise


@handler("render_project")
def render_project(db: Session, job: Job) -> dict:
    """Re-render a project from its saved Scene JSON (used by the editor)."""
    proj = db.get(Project, job.payload["project_id"])
    proj.status = "rendering"
    db.commit()
    try:
        return _render_and_save(db, job, SceneProject.model_validate(proj.scene_json), proj)
    except Exception:
        proj.status = "done" if proj.output_path else "failed"  # never leave the editor locked
        db.commit()
        raise


@handler("regen_voice")
def regen_voice(db: Session, job: Job) -> dict:
    """Re-voice every scene of a project with a new voice/speed, keeping text and visuals."""
    from clue.ai.align import align
    from clue.ai.tts import get_tts
    from clue.core.media import duration
    from clue.jobs.text_story import PAD
    from clue.models import ProjectVersion

    p = job.payload
    proj = db.get(Project, p["project_id"])
    if proj is None or proj.user_id != job.user_id or not proj.scene_json:
        raise styles.SpecError("That project was not found.")
    sj = proj.scene_json
    tts, d = get_tts(), storage.user_dir(job.user_id, f"edits/{proj.id}")
    n = len(sj["scenes"])
    new_scenes = []
    for i, sc in enumerate(sj["scenes"]):
        queue.progress(db, job.id, 5 + int(90 * i / n), f"voice {i + 1}/{n}")
        wav = d / f"{job.id}_{i}.wav"
        tts.synthesize(sc["text"], p["voice"], float(p.get("speed", 1.0)), wav)
        dur = duration(wav) + PAD
        new_scenes.append({**sc, "audio_path": f"{job.user_id}/edits/{proj.id}/{wav.name}", "duration": round(dur, 3),
                           "words": [w.model_dump() for w in align(sc["text"], wav, dur)]})
    db.add(ProjectVersion(project_id=proj.id, version=proj.version, scene_json=proj.scene_json))
    proj.scene_json = {**sj, "scenes": new_scenes}
    proj.version += 1
    db.commit()
    _settle(db, job)
    return {"project_id": proj.id, "version": proj.version}


@handler("make_proxy")
def make_proxy(db: Session, job: Job) -> dict:
    """480p preview copy of an uploaded video so the editor stays light on weak connections."""
    from clue.core.media import run_ffmpeg

    a = db.get(Asset, job.payload["asset_id"])
    if a is None or a.kind != "video":
        return {"skipped": True}
    rel = f"{a.user_id}/proxy/{a.id}.mp4"
    out = storage.root() / rel
    out.parent.mkdir(parents=True, exist_ok=True)
    run_ffmpeg(["-i", str(storage.safe_path(a.path)), "-vf", "scale=-2:480", "-c:v", "libx264", "-preset", "ultrafast", "-crf", "30",
                "-c:a", "aac", "-b:a", "64k", "-ac", "1", "-movflags", "+faststart", str(out)], timeout=1800)
    a.proxy_path = rel
    db.commit()
    return {"proxy": rel}


import clue.jobs.clip_handlers  # noqa: E402,F401  (registers transcription / auto-clip handlers)


def recover_stale(db: Session) -> None:
    """Jobs left 'running' by a crashed worker go back to the queue."""
    for j in db.scalars(select(Job).where(Job.status == "running")).all():
        queue.fail(db, j.id, "worker restarted")
