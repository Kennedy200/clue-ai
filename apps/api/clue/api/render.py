"""Render jobs: create, status, SSE progress, cancel, download."""
from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from clue.api.deps import current_user
from clue.core import credits, storage
from clue.core.config import get_settings
from clue.core.db import SessionLocal, get_db
from clue.core.ids import new_id
from clue.jobs import queue
from clue.models import Job, Plan, Project, User
from clue.render.scene import CaptionStyle

router = APIRouter(tags=["render"])
RENDER_COST = {"fast": 5, "pro": 8, "cinematic": 14}


class TextStory(BaseModel):
    title: str = Field(default="Untitled story", max_length=200)
    text: str = Field(min_length=5, max_length=6000)
    voice: str = "af_heart"
    speed: float = Field(default=1.0, ge=0.5, le=2.0)
    seed: int = 0
    caption: CaptionStyle = CaptionStyle()


def _watermark(u: User, db: Session) -> str | None:
    if get_settings().app_mode == "self_host":
        return None
    plan = db.get(Plan, u.plan_id)
    return "Made with Clue AI" if plan and plan.features.get("watermark") else None


@router.get("/render/cost")
def cost(mode: str = "fast"):
    return {"mode": mode, "credits": RENDER_COST.get(mode, 5)}


STYLE_NAMES = ["text_story", "video_story", "commentary", "split_screen", "ranking"]


class CreateVideo(BaseModel):
    style: str
    title: str = Field(default="Untitled video", max_length=200)
    spec: dict = Field(default_factory=dict)
    voice: str = "af_heart"
    speed: float = Field(default=1.0, ge=0.5, le=2.0)
    seed: int = 0
    mode: str = "fast"
    music_asset_id: str | None = None
    caption: CaptionStyle = CaptionStyle()


def _allowed_modes(u: User, db: Session) -> list[str]:
    if get_settings().app_mode == "self_host":
        return ["fast", "pro", "cinematic"]
    plan = db.get(Plan, u.plan_id)
    return (plan.features.get("modes") if plan else None) or ["fast"]


@router.post("/render/create")
def create_video(body: CreateVideo, u: User = Depends(current_user), db: Session = Depends(get_db)):
    if body.style not in STYLE_NAMES:
        raise HTTPException(422, "Unknown video style.")
    if body.mode not in RENDER_COST:
        raise HTTPException(422, "Unknown render mode.")
    if body.mode not in _allowed_modes(u, db):
        raise HTTPException(403, f"{body.mode.title()} mode is not included in your plan. Upgrade to use it.")
    proj = Project(user_id=u.id, title=body.title.strip() or "Untitled video", style=body.style)
    db.add(proj)
    db.commit()
    ref = new_id()
    try:
        credits.reserve(db, u.id, RENDER_COST[body.mode], f"render {body.mode}", ref_id=ref)
    except credits.InsufficientCredits:
        db.delete(proj)
        db.commit()
        raise HTTPException(402, f"Not enough credits. This costs {RENDER_COST[body.mode]}; you have {credits.balance(db, u.id)}.")
    job = queue.enqueue(db, "render_video", {
        "project_id": proj.id, "style": body.style, "spec": body.spec, "voice": body.voice, "speed": body.speed, "seed": body.seed,
        "mode": body.mode, "music_asset_id": body.music_asset_id, "caption": body.caption.model_dump(), "watermark": _watermark(u, db),
    }, user_id=u.id, credit_ref=ref)
    return {"job_id": job.id, "project_id": proj.id, "credits": RENDER_COST[body.mode]}


@router.post("/render/text-story")
def create_text_story(body: TextStory, u: User = Depends(current_user), db: Session = Depends(get_db)):
    mode = "fast"
    proj = Project(user_id=u.id, title=body.title.strip() or "Untitled story", style="text_story")
    db.add(proj)
    db.commit()
    ref = new_id()
    try:
        credits.reserve(db, u.id, RENDER_COST[mode], "render fast", ref_id=ref)
    except credits.InsufficientCredits:
        db.delete(proj)
        db.commit()
        raise HTTPException(402, f"Not enough credits. This costs {RENDER_COST[mode]}; you have {credits.balance(db, u.id)}.")
    job = queue.enqueue(db, "render_text_story", {
        "project_id": proj.id, "text": body.text, "voice": body.voice, "speed": body.speed, "seed": body.seed,
        "caption": body.caption.model_dump(), "watermark": _watermark(u, db), "mode": mode,
    }, user_id=u.id, credit_ref=ref)
    return {"job_id": job.id, "project_id": proj.id, "credits": RENDER_COST[mode]}


def _job_for(db: Session, job_id: str, u: User) -> Job:
    j = db.get(Job, job_id)
    if j is None or j.user_id != u.id:
        raise HTTPException(404, "Job not found.")
    return j


def _view(j: Job) -> dict:
    return {"id": j.id, "type": j.type, "status": j.status, "progress": j.progress, "stage": j.stage,
            "error": j.error if j.status == "failed" else None, "result": j.result}


@router.get("/jobs/{job_id}")
def job_status(job_id: str, u: User = Depends(current_user), db: Session = Depends(get_db)):
    return _view(_job_for(db, job_id, u))


@router.get("/jobs/{job_id}/events")
async def job_events(job_id: str, u: User = Depends(current_user), db: Session = Depends(get_db)):
    _job_for(db, job_id, u)

    async def gen():
        last = None
        while True:
            with SessionLocal() as s:
                j = s.get(Job, job_id)
                view = _view(j) if j else {"status": "failed", "error": "Job not found."}
            payload = json.dumps(view)
            if payload != last:
                yield f"data: {payload}\n\n"
                last = payload
            if view["status"] in ("done", "failed", "cancelled"):
                return
            await asyncio.sleep(0.7)

    return StreamingResponse(gen(), media_type="text/event-stream", headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"})


@router.post("/jobs/{job_id}/cancel")
def job_cancel(job_id: str, u: User = Depends(current_user), db: Session = Depends(get_db)):
    j = _job_for(db, job_id, u)
    queue.cancel(db, j.id)
    if j.credit_ref:
        credits.refund(db, u.id, j.credit_ref)
    return {"ok": True}


@router.get("/projects")
def list_projects(u: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.query(Project).filter(Project.user_id == u.id).order_by(Project.id.desc()).limit(100).all()
    return [{"id": p.id, "title": p.title, "style": p.style, "status": p.status, "duration_ms": p.duration, "created_at": p.created_at.isoformat()} for p in rows]


@router.get("/projects/{pid}/download-url")
def download_url(pid: str, u: User = Depends(current_user), db: Session = Depends(get_db)):
    p = db.get(Project, pid)
    if p is None or p.user_id != u.id or not p.output_path:
        raise HTTPException(404, "No finished video for this project.")
    return {"url": f"/api/files?path={p.output_path}&t={storage.sign(p.output_path, 900)}"}


@router.get("/files/sign")
def sign_file(path: str, u: User = Depends(current_user)):
    """Signed link for one of the caller's own files (outputs, uploads, clips). Other users' paths are refused."""
    try:
        f = storage.safe_path(path)
    except ValueError:
        raise HTTPException(400, "Bad path.")
    if not path.startswith(f"{u.id}/") or not f.is_file():
        raise HTTPException(404, "File not found.")
    return {"url": f"/api/files?path={path}&t={storage.sign(path, 900)}"}


@router.get("/files")
def get_file(path: str, t: str):
    """Download via a signed, expiring link (works in a plain <a href> or <video src>)."""
    if not storage.verify(path, t):
        raise HTTPException(403, "This link has expired. Request a new one.")
    try:
        f = storage.safe_path(path)
    except ValueError:
        raise HTTPException(400, "Bad path.")
    if not f.is_file():
        raise HTTPException(404, "File not found.")
    import mimetypes

    return FileResponse(f, media_type=mimetypes.guess_type(f.name)[0] or "application/octet-stream", filename=f.name)


@router.get("/voices")
def voices(u: User = Depends(current_user)):
    from clue.ai.tts import TTSError, get_tts

    try:
        return get_tts().voices()
    except TTSError as e:
        raise HTTPException(503, str(e))
