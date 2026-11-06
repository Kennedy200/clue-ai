"""Resumable chunked uploads + media library.

Protocol (tus-like): POST /uploads/init -> id; PUT /uploads/{id}?offset=N with raw bytes (append at N);
GET /uploads/{id} -> current offset (resume after a dropped connection); POST /uploads/{id}/finish -> validated Asset.
"""
from __future__ import annotations

import json
import re
import shutil

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from clue.api.deps import current_user
from clue.core import storage
from clue.core.config import get_settings
from clue.core.db import get_db
from clue.core.ids import new_id
from clue.core.media import MediaError, probe, run_ffmpeg
from clue.models import Asset, Plan, User

router = APIRouter(tags=["uploads"])
ALLOWED = {"mp4", "mov", "webm", "mkv", "m4v", "mp3", "wav", "m4a", "aac", "ogg", "jpg", "jpeg", "png", "webp"}
MB = 1024 * 1024


def _limits(u: User, db: Session) -> tuple[int, int]:
    """(max single file bytes, total quota bytes)."""
    if get_settings().app_mode == "self_host":
        return 4096 * MB, 100_000 * MB
    plan = db.get(Plan, u.plan_id)
    big = plan is not None and plan.id != "free"
    return (1024 * MB, 20_000 * MB) if big else (200 * MB, 1_000 * MB)


def _tmp():
    d = get_settings().storage_dir / "uploads_tmp"
    d.mkdir(parents=True, exist_ok=True)
    return d


class Init(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    size: int = Field(gt=0)


def _meta(upload_id: str, u: User) -> dict:
    if not re.fullmatch(r"[0-9A-Z]{26}", upload_id):
        raise HTTPException(404, "Upload not found.")
    f = _tmp() / f"{upload_id}.json"
    if not f.exists():
        raise HTTPException(404, "Upload not found.")
    m = json.loads(f.read_text())
    if m["user"] != u.id:
        raise HTTPException(404, "Upload not found.")
    return m


@router.post("/uploads/init")
def init(body: Init, u: User = Depends(current_user), db: Session = Depends(get_db)):
    ext = body.name.rsplit(".", 1)[-1].lower() if "." in body.name else ""
    if ext not in ALLOWED:
        raise HTTPException(415, f"This file type is not supported. Use one of: {', '.join(sorted(ALLOWED))}.")
    one, quota = _limits(u, db)
    if body.size > one:
        raise HTTPException(413, f"This file is larger than your {one // MB} MB limit.")
    used = db.scalar(select(func.coalesce(func.sum(Asset.size), 0)).where(Asset.user_id == u.id)) or 0
    if used + body.size > quota:
        raise HTTPException(413, "You are over your storage quota. Delete some media first.")
    uid = new_id()
    (_tmp() / f"{uid}.json").write_text(json.dumps({"user": u.id, "name": body.name[:200], "size": body.size, "ext": ext}))
    (_tmp() / f"{uid}.part").write_bytes(b"")
    return {"id": uid, "offset": 0, "chunk_size": 4 * MB}


@router.get("/uploads/{upload_id}")
def status(upload_id: str, u: User = Depends(current_user)):
    m = _meta(upload_id, u)
    return {"id": upload_id, "offset": (_tmp() / f"{upload_id}.part").stat().st_size, "size": m["size"]}


@router.put("/uploads/{upload_id}")
async def chunk(upload_id: str, request: Request, offset: int, u: User = Depends(current_user)):
    m = _meta(upload_id, u)
    part = _tmp() / f"{upload_id}.part"
    have = part.stat().st_size
    if offset != have:
        raise HTTPException(409, f"Offset mismatch: the server has {have} bytes. Resume from there.")
    data = await request.body()
    if have + len(data) > m["size"]:
        raise HTTPException(413, "More data than the declared size.")
    with open(part, "ab") as f:
        f.write(data)
    return {"offset": have + len(data)}


def _view(a: Asset) -> dict:
    return {"id": a.id, "kind": a.kind, "name": a.name, "path": a.path, "duration": a.duration, "width": a.width, "height": a.height,
            "has_audio": a.has_audio, "size": a.size, "provider": a.provider, "attribution": a.attribution, "created_at": a.created_at.isoformat()}


@router.post("/uploads/{upload_id}/finish")
def finish(upload_id: str, u: User = Depends(current_user), db: Session = Depends(get_db)):
    m = _meta(upload_id, u)
    part = _tmp() / f"{upload_id}.part"
    if part.stat().st_size != m["size"]:
        raise HTTPException(409, f"Upload incomplete ({part.stat().st_size}/{m['size']} bytes). Resume it.")
    try:
        info = probe(part)
    except MediaError:
        _cleanup(upload_id)
        raise HTTPException(422, "This file could not be read as a video, audio or image file.")
    vs = [s for s in info["streams"] if s["codec_type"] == "video"]
    au = [s for s in info["streams"] if s["codec_type"] == "audio"]
    if m["ext"] in {"jpg", "jpeg", "png", "webp"}:
        if not vs:
            _cleanup(upload_id)
            raise HTTPException(422, "This does not look like an image.")
        kind = "image"
    elif vs and not (len(vs) == 1 and vs[0].get("codec_name") in ("mjpeg", "png") and au):
        kind = "video"
    elif au:
        kind = "audio"
    else:
        _cleanup(upload_id)
        raise HTTPException(422, "No video, audio or image found in this file.")
    dur = float(info["format"].get("duration") or 0) or None
    aid = new_id()
    out_ext = "jpg" if kind == "image" and m["ext"] in ("jpg", "jpeg") else m["ext"]
    rel = f"{u.id}/uploads/{aid}.{out_ext}"
    dest = storage.root() / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:  # strip metadata (GPS, device info) without re-encoding
        run_ffmpeg(["-i", str(part), "-map_metadata", "-1", "-map", "0", "-c", "copy", str(dest)], timeout=1800)
    except MediaError:
        shutil.copyfile(part, dest)  # some containers cannot be stream-copied; keep the file as is
    a = Asset(id=aid, user_id=u.id, kind=kind, name=m["name"], path=rel, duration=dur, width=int(vs[0]["width"]) if vs else None,
              height=int(vs[0]["height"]) if vs else None, has_audio=bool(au), size=dest.stat().st_size)
    db.add(a)
    db.commit()
    _cleanup(upload_id)
    return _view(a)


def _cleanup(upload_id: str) -> None:
    for ext in ("json", "part"):
        (_tmp() / f"{upload_id}.{ext}").unlink(missing_ok=True)


@router.get("/media")
def library(kind: str | None = None, u: User = Depends(current_user), db: Session = Depends(get_db)):
    q = select(Asset).where(Asset.user_id == u.id).order_by(Asset.id.desc()).limit(200)
    if kind:
        q = q.where(Asset.kind == kind)
    return [_view(a) for a in db.scalars(q)]


@router.delete("/media/{asset_id}")
def delete_media(asset_id: str, u: User = Depends(current_user), db: Session = Depends(get_db)):
    a = db.get(Asset, asset_id)
    if a is None or a.user_id != u.id:
        raise HTTPException(404, "Media not found.")
    (storage.root() / a.path).unlink(missing_ok=True)
    db.delete(a)
    db.commit()
    return {"ok": True}


@router.get("/media/{asset_id}/url")
def media_url(asset_id: str, u: User = Depends(current_user), db: Session = Depends(get_db)):
    a = db.get(Asset, asset_id)
    if a is None or a.user_id != u.id:
        raise HTTPException(404, "Media not found.")
    return {"url": f"/api/files?path={a.path}&t={storage.sign(a.path, 900)}"}
