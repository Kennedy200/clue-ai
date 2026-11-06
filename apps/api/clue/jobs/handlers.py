"""Job handlers registered with the worker."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from clue.core import credits
from clue.core.db import SessionLocal
from clue.jobs import queue
from clue.jobs.text_story import build_project, output_path
from clue.models import Job, Project
from clue.render.compiler import RenderCancelled, render
from clue.render.scene import CaptionStyle, SceneProject
from clue.jobs.registry import handler


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


@handler("render_project")
def render_project(db: Session, job: Job) -> dict:
    """Re-render a project from its saved Scene JSON (used by the editor)."""
    proj = db.get(Project, job.payload["project_id"])
    proj.status = "rendering"
    db.commit()
    return _render_and_save(db, job, SceneProject.model_validate(proj.scene_json), proj)


def recover_stale(db: Session) -> None:
    """Jobs left 'running' by a crashed worker go back to the queue."""
    for j in db.scalars(select(Job).where(Job.status == "running")).all():
        queue.fail(db, j.id, "worker restarted")
