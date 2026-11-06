"""Editor API: load/save Scene JSON with conflict-safe versions, voice regeneration, visual search/import, render."""
from __future__ import annotations

import math
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from clue.api.deps import current_user
from clue.api.render import RENDER_COST, _allowed_modes, _watermark
from clue.assets.providers import PROVIDERS, AssetError, AssetResult, fetch
from clue.core import credits, storage
from clue.core.db import get_db
from clue.core.ids import new_id
from clue.core.media import MediaError, duration
from clue.jobs import queue
from clue.models import Asset, Project, ProjectVersion, User
from clue.render.scene import SceneProject

router = APIRouter(tags=["editor"])
KEEP_VERSIONS = 30
IMPORT_HOSTS = {"upload.wikimedia.org", "thumb.wikimedia.org", "commons.wikimedia.org", "image.pollinations.ai"}  # exactly the hosts our providers return


def _project(db: Session, pid: str, u: User) -> Project:
    p = db.get(Project, pid)
    if p is None or p.user_id != u.id:
        raise HTTPException(404, "Project not found.")
    return p


def _paths(sp: SceneProject) -> list[str]:
    out = []
    for s in sp.scenes:
        if s.audio_path:
            out.append(s.audio_path)
        for v in (s.visual, s.visual2):
            if v and v.path:
                out.append(v.path)
    if sp.music_path:
        out.append(sp.music_path)
    return out


def _check_paths(sp: SceneProject, u: User) -> None:
    """Every file a project references must belong to this user (or be a shared visual cache). Stops cross-user file access."""
    for p in _paths(sp):
        try:
            storage.safe_path(p)
        except ValueError:
            raise HTTPException(422, "A file path in this project is not allowed.")
        if not (p.startswith(f"{u.id}/") or p.startswith("cache/assets/")):
            raise HTTPException(422, "This project references a file that is not yours.")


def _file_urls(db: Session, sp: SceneProject, u: User) -> dict[str, str]:
    """Signed URLs for everything the browser preview needs. Uploaded videos use their 480p proxy when it exists."""
    urls: dict[str, str] = {}
    proxies = {a.path: a.proxy_path for a in db.scalars(select(Asset).where(Asset.user_id == u.id, Asset.proxy_path.is_not(None)))}
    for p in set(_paths(sp)):
        use = proxies.get(p) or p
        if (storage.root() / use).is_file():
            urls[p] = f"/api/files?path={use}&t={storage.sign(use, 3600)}"
    return urls


def _view(db: Session, p: Project, u: User) -> dict:
    sp = SceneProject.model_validate(p.scene_json) if p.scene_json else None
    out = None
    if p.output_path and (storage.root() / p.output_path).is_file():
        out = f"/api/files?path={p.output_path}&t={storage.sign(p.output_path, 900)}"
    return {"id": p.id, "title": p.title, "style": p.style, "status": p.status, "version": p.version,
            "scene": sp.model_dump() if sp else None, "files": _file_urls(db, sp, u) if sp else {}, "output_url": out}


@router.get("/projects/{pid}")
def get_project(pid: str, u: User = Depends(current_user), db: Session = Depends(get_db)):
    p = _project(db, pid, u)
    if p.scene_json is None:
        raise HTTPException(409, "This video has no editable scenes yet (it may still be rendering or it failed).")
    return _view(db, p, u)


class Save(BaseModel):
    scene: dict
    base_version: int
    title: str | None = Field(default=None, max_length=200)


@router.put("/projects/{pid}/scene")
def save_scene(pid: str, body: Save, u: User = Depends(current_user), db: Session = Depends(get_db)):
    p = _project(db, pid, u)
    if p.status == "rendering":
        raise HTTPException(409, "This video is rendering. Wait for it to finish, then edit.")
    if body.base_version != p.version:
        raise HTTPException(409, f"This project changed elsewhere (version {p.version}, you had {body.base_version}). Reload to continue.")
    try:
        sp = SceneProject.model_validate(body.scene)
    except ValidationError as e:
        raise HTTPException(422, f"Invalid scene data: {e.errors()[0]['loc']} {e.errors()[0]['msg']}")
    if not sp.scenes:
        raise HTTPException(422, "A video needs at least one scene.")
    _check_paths(sp, u)
    if p.scene_json:
        db.add(ProjectVersion(project_id=p.id, version=p.version, scene_json=p.scene_json))
    p.scene_json = sp.model_dump()
    p.version += 1
    if body.title:
        p.title = body.title.strip() or p.title
    p.duration = int(sp.total_duration() * 1000)
    old = db.scalars(select(ProjectVersion).where(ProjectVersion.project_id == p.id).order_by(ProjectVersion.id.desc()).offset(KEEP_VERSIONS)).all()
    for o in old:
        db.delete(o)
    db.commit()
    return {"version": p.version}


@router.get("/projects/{pid}/versions")
def versions(pid: str, u: User = Depends(current_user), db: Session = Depends(get_db)):
    p = _project(db, pid, u)
    rows = db.scalars(select(ProjectVersion).where(ProjectVersion.project_id == p.id).order_by(ProjectVersion.id.desc()).limit(KEEP_VERSIONS)).all()
    return [{"id": r.id, "version": r.version, "at": r.created_at.isoformat(), "scenes": len(r.scene_json.get("scenes", []))} for r in rows]


@router.post("/projects/{pid}/versions/{vid}/restore")
def restore(pid: str, vid: str, u: User = Depends(current_user), db: Session = Depends(get_db)):
    p = _project(db, pid, u)
    v = db.get(ProjectVersion, vid)
    if v is None or v.project_id != p.id:
        raise HTTPException(404, "Version not found.")
    db.add(ProjectVersion(project_id=p.id, version=p.version, scene_json=p.scene_json))
    p.scene_json = v.scene_json
    p.version += 1
    db.commit()
    return _view(db, p, u)


@router.delete("/projects/{pid}")
def delete_project(pid: str, u: User = Depends(current_user), db: Session = Depends(get_db)):
    p = _project(db, pid, u)
    if p.output_path:
        (storage.root() / p.output_path).unlink(missing_ok=True)
    db.delete(p)
    db.commit()
    return {"ok": True}


class VoiceReq(BaseModel):
    text: str = Field(min_length=1, max_length=1200)
    voice: str = "af_heart"
    speed: float = Field(default=1.0, ge=0.5, le=2.0)


@router.post("/projects/{pid}/scene-voice")
def scene_voice(pid: str, body: VoiceReq, u: User = Depends(current_user), db: Session = Depends(get_db)):
    """Re-voice one scene: new audio, the real measured duration and fresh word timings. Costs 1 credit."""
    from clue.ai.align import align
    from clue.ai.tts import TTSError, get_tts
    from clue.jobs.text_story import PAD

    _project(db, pid, u)
    wav = storage.user_dir(u.id, f"edits/{pid}") / f"{new_id()}.wav"
    try:
        with credits.spend(db, u.id, 1, "re-voice scene"):
            get_tts().synthesize(body.text, body.voice, body.speed, wav)
            dur = duration(wav) + PAD
            words = align(body.text, wav, dur)
    except credits.InsufficientCredits:
        raise HTTPException(402, f"Not enough credits. This costs 1; you have {credits.balance(db, u.id)}.")
    except (TTSError, MediaError) as e:
        raise HTTPException(503, str(e))
    return {"audio_path": f"{u.id}/edits/{pid}/{wav.name}", "duration": round(dur, 3), "words": [w.model_dump() for w in words],
            "url": f"/api/files?path={u.id}/edits/{pid}/{wav.name}&t={storage.sign(f'{u.id}/edits/{pid}/{wav.name}', 3600)}"}


class VoiceAll(BaseModel):
    voice: str
    speed: float = Field(default=1.0, ge=0.5, le=2.0)


@router.post("/projects/{pid}/regen-voice")
def regen_all(pid: str, body: VoiceAll, u: User = Depends(current_user), db: Session = Depends(get_db)):
    p = _project(db, pid, u)
    if not p.scene_json:
        raise HTTPException(409, "Nothing to re-voice yet.")
    words = sum(len(s["text"].split()) for s in p.scene_json["scenes"])
    cost = max(1, math.ceil(words / 75))
    ref = new_id()
    try:
        credits.reserve(db, u.id, cost, "re-voice video", ref)
    except credits.InsufficientCredits:
        raise HTTPException(402, f"Not enough credits. This costs {cost}; you have {credits.balance(db, u.id)}.")
    job = queue.enqueue(db, "regen_voice", {"project_id": p.id, "voice": body.voice, "speed": body.speed}, user_id=u.id, credit_ref=ref)
    return {"job_id": job.id, "credits": cost}


class AssetSearch(BaseModel):
    q: str = Field(min_length=2, max_length=120)
    source: str = Field(default="photos", pattern="^(photos|ai)$")


@router.post("/assets/search")
def search_assets(body: AssetSearch, u: User = Depends(current_user)):
    prov = PROVIDERS["wikimedia" if body.source == "photos" else "pollinations"]
    try:
        res = prov.search(body.q if body.source == "photos" else f"{body.q}, vertical, cinematic, no text", 8 if body.source == "photos" else 1)
    except AssetError as e:
        raise HTTPException(503, str(e))
    return [{"provider": r.provider, "url": r.url, "title": r.title, "author": r.author, "license": r.license, "page_url": r.page_url} for r in res]


class Import(BaseModel):
    provider: str
    url: str = Field(max_length=1000)
    title: str = Field(default="", max_length=200)
    author: str = Field(default="", max_length=200)
    license: str = Field(default="", max_length=100)
    page_url: str = Field(default="", max_length=500)


@router.post("/assets/import")
def import_asset(body: Import, u: User = Depends(current_user), db: Session = Depends(get_db)):
    """Download a chosen search result into the user's library (with licence/attribution). Host allow-list prevents SSRF."""
    host = urlparse(body.url)
    if host.scheme != "https" or host.hostname not in IMPORT_HOSTS or body.provider not in PROVIDERS:
        raise HTTPException(422, "That image source is not allowed.")
    try:
        rel = fetch(AssetResult(body.provider, body.url, body.title, body.author, body.license, body.page_url), u.id, timeout=90)
    except AssetError as e:
        raise HTTPException(503, str(e))
    a = Asset(user_id=u.id, kind="image", name=(body.title or "image")[:200], path=rel, size=(storage.root() / rel).stat().st_size, provider=body.provider,
              attribution=AssetResult(body.provider, body.url, body.title, body.author, body.license, body.page_url).attribution)
    db.add(a)
    db.commit()
    return {"id": a.id, "path": rel, "attribution": a.attribution}


class RenderReq(BaseModel):
    mode: str = "fast"


@router.post("/projects/{pid}/render")
def render_again(pid: str, body: RenderReq, u: User = Depends(current_user), db: Session = Depends(get_db)):
    p = _project(db, pid, u)
    if not p.scene_json:
        raise HTTPException(409, "Nothing to render.")
    if p.status == "rendering":
        raise HTTPException(409, "This video is already rendering.")
    if body.mode not in RENDER_COST:
        raise HTTPException(422, "Unknown render mode.")
    if body.mode not in _allowed_modes(u, db):
        raise HTTPException(403, f"{body.mode.title()} mode is not included in your plan. Upgrade to use it.")
    sp = SceneProject.model_validate(p.scene_json)
    sp.mode, sp.watermark = body.mode, _watermark(u, db)  # type: ignore[assignment]
    if sp.total_duration() > {"fast": 60, "pro": 180, "cinematic": 180}[body.mode] + 0.5:
        raise HTTPException(422, f"This video is {sp.total_duration():.0f}s, longer than {body.mode} mode allows. Shorten it or pick Pro.")
    _check_paths(sp, u)
    ref = new_id()
    try:
        credits.reserve(db, u.id, RENDER_COST[body.mode], f"render {body.mode}", ref)
    except credits.InsufficientCredits:
        raise HTTPException(402, f"Not enough credits. This costs {RENDER_COST[body.mode]}; you have {credits.balance(db, u.id)}.")
    p.scene_json = sp.model_dump()
    db.commit()
    job = queue.enqueue(db, "render_project", {"project_id": p.id}, user_id=u.id, credit_ref=ref)
    return {"job_id": job.id, "credits": RENDER_COST[body.mode]}

