"""Standalone tools: transcriber (SRT/VTT), Auto Clipping."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from clue.ai.transcribe import to_srt, to_vtt
from clue.api.deps import current_user
from clue.api.render import _watermark
from clue.core import credits, storage
from clue.core.db import get_db
from clue.core.ids import new_id
from clue.jobs import queue
from clue.models import Asset, Clip, Transcript, User

router = APIRouter(tags=["tools"])
COST = {"autoclip_analyze": 8, "autoclip_export": 2}


def _own(db: Session, model, id_: str, u: User, what: str):
    row = db.get(model, id_)
    if row is None or row.user_id != u.id:
        raise HTTPException(404, f"{what} not found.")
    return row


def _enqueue(db: Session, u: User, type_: str, payload: dict, cost: int = 0, reason: str = "") -> dict:
    ref = None
    if cost:
        ref = new_id()
        try:
            credits.reserve(db, u.id, cost, reason or type_, ref_id=ref)
        except credits.InsufficientCredits:
            raise HTTPException(402, f"Not enough credits. This costs {cost}; you have {credits.balance(db, u.id)}.")
    job = queue.enqueue(db, type_, payload, user_id=u.id, credit_ref=ref)
    return {"job_id": job.id, "credits": cost}


class TranscribeReq(BaseModel):
    asset_id: str
    language: str | None = Field(default=None, max_length=8)


@router.post("/tools/transcribe")
def transcribe_start(body: TranscribeReq, u: User = Depends(current_user), db: Session = Depends(get_db)):
    a = _own(db, Asset, body.asset_id, u, "Media")
    if a.kind not in ("video", "audio"):
        raise HTTPException(422, "Pick a video or audio file.")
    return _enqueue(db, u, "transcribe", {"asset_id": a.id, "language": body.language})


@router.get("/transcripts/{tid}")
def transcript(tid: str, u: User = Depends(current_user), db: Session = Depends(get_db)):
    t = _own(db, Transcript, tid, u, "Transcript")
    return {"id": t.id, "asset_id": t.asset_id, "language": t.language, "words": t.words, "segments": t.segments}


class WordsEdit(BaseModel):
    words: list[dict] = Field(max_length=100_000)


@router.put("/transcripts/{tid}")
def transcript_edit(tid: str, body: WordsEdit, u: User = Depends(current_user), db: Session = Depends(get_db)):
    t = _own(db, Transcript, tid, u, "Transcript")
    clean = []
    for w in body.words:
        try:
            clean.append({"w": str(w["w"])[:80], "start": float(w["start"]), "end": float(w["end"])})
        except (KeyError, TypeError, ValueError):
            raise HTTPException(422, "Each word needs w, start and end.")
    t.words = clean
    db.commit()
    return {"ok": True, "words": len(clean)}


@router.get("/transcripts/{tid}/download")
def transcript_download(tid: str, fmt: str = "srt", u: User = Depends(current_user), db: Session = Depends(get_db)):
    t = _own(db, Transcript, tid, u, "Transcript")
    if fmt == "srt":
        body, mt = to_srt(t.words), "application/x-subrip"
    elif fmt == "vtt":
        body, mt = to_vtt(t.words), "text/vtt"
    elif fmt == "txt":
        body, mt = " ".join(w["w"] for w in t.words), "text/plain"
    else:
        raise HTTPException(422, "Format must be srt, vtt or txt.")
    return PlainTextResponse(body, media_type=f"{mt}; charset=utf-8", headers={"Content-Disposition": f"attachment; filename=transcript.{fmt}"})


class AnalyzeReq(BaseModel):
    asset_id: str
    count: int = Field(default=8, ge=1, le=20)


@router.post("/autoclip/analyze")
def analyze(body: AnalyzeReq, u: User = Depends(current_user), db: Session = Depends(get_db)):
    a = _own(db, Asset, body.asset_id, u, "Media")
    if a.kind != "video" or not a.has_audio:
        raise HTTPException(422, "Pick a video that has speech (an audio track).")
    return _enqueue(db, u, "autoclip_analyze", {"asset_id": a.id, "n": body.count}, COST["autoclip_analyze"], "auto-clip analysis")


def _clip_view(c: Clip) -> dict:
    thumb = f"{c.user_id}/clips/{c.id}.jpg"
    exists = (storage.root() / thumb).exists()
    return {"id": c.id, "asset_id": c.asset_id, "start": c.start, "end": c.end, "length": round(c.end - c.start, 1), "score": c.score,
            "reason": c.reason, "title": c.title, "hook": c.hook, "scorer": c.scorer, "exported": bool(c.output_path),
            "thumb_url": f"/api/files?path={thumb}&t={storage.sign(thumb, 900)}" if exists else None}


@router.get("/autoclip/{asset_id}/clips")
def clips(asset_id: str, u: User = Depends(current_user), db: Session = Depends(get_db)):
    _own(db, Asset, asset_id, u, "Media")
    rows = db.scalars(select(Clip).where(Clip.asset_id == asset_id, Clip.user_id == u.id).order_by(Clip.score.desc())).all()
    return [_clip_view(c) for c in rows]


class ExportReq(BaseModel):
    clip_id: str
    reframe: str = Field(default="face", pattern="^(face|blur|center)$")
    captions: bool = True


@router.post("/autoclip/export")
def export(body: ExportReq, u: User = Depends(current_user), db: Session = Depends(get_db)):
    c = _own(db, Clip, body.clip_id, u, "Clip")
    return _enqueue(db, u, "autoclip_export", {"clip_id": c.id, "reframe": body.reframe, "captions": body.captions, "watermark": _watermark(u, db)},
                    COST["autoclip_export"], "export clip")


@router.get("/autoclip/clips/{clip_id}/download-url")
def clip_url(clip_id: str, u: User = Depends(current_user), db: Session = Depends(get_db)):
    c = _own(db, Clip, clip_id, u, "Clip")
    if not c.output_path:
        raise HTTPException(404, "Export this clip first.")
    return {"url": f"/api/files?path={c.output_path}&t={storage.sign(c.output_path, 900)}"}
