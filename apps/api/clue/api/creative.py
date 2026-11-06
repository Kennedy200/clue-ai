"""Creative tools: ideas, title scorer, script enhancer, thumbnails, voiceover, voice previews. Each shows its credit cost."""
from __future__ import annotations

import math
from contextlib import contextmanager

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from clue.ai.llm import LLMError
from clue.ai.prompts import tools as P
from clue.api.deps import current_user
from clue.api.tools import _enqueue, _own
from clue.core import credits, storage
from clue.core.config import get_settings
from clue.core.db import get_db
from clue.core.ids import new_id
from clue.models import Asset, User

router = APIRouter(tags=["creative"])
COST = {"ideas": 1, "title": 1, "enhance": 1, "thumbnails": 2, "plan": 1}


@router.get("/credits/costs")
def costs():
    return {**COST, "render_fast": 5, "render_pro": 8, "render_cinematic": 14, "voiceover_per_30s": 1, "autoclip_analyze": 8, "autoclip_export": 2}


@contextmanager
def _guard(db: Session, u: User, amount: int, what: str):
    """Charge for an action (refunded automatically if the body raises); lack of credits becomes a friendly 402."""
    try:
        with credits.spend(db, u.id, amount, what):
            yield
    except credits.InsufficientCredits:
        raise HTTPException(402, f"Not enough credits. This costs {amount}; you have {credits.balance(db, u.id)}.")


class IdeasReq(BaseModel):
    niche: str = Field(min_length=2, max_length=300)
    audience: str = Field(default="", max_length=300)
    tone: str = "standard"


@router.post("/ai/ideas", response_model=P.Ideas)
def ideas(body: IdeasReq, u: User = Depends(current_user), db: Session = Depends(get_db)):
    try:
        with _guard(db, u, COST["ideas"], "ideas"):
            return P.ideas(db, body.niche, body.audience, body.tone, u.id)
    except LLMError as e:
        raise HTTPException(503, str(e))


class TitleReq(BaseModel):
    title: str = Field(min_length=3, max_length=200)


@router.post("/ai/title-score", response_model=P.TitleScore)
def title_score(body: TitleReq, u: User = Depends(current_user), db: Session = Depends(get_db)):
    try:
        with _guard(db, u, COST["title"], "title score"):
            return P.score_title(db, body.title, u.id)
    except LLMError as e:
        raise HTTPException(503, str(e))


class EnhanceReq(BaseModel):
    script: str = Field(min_length=10, max_length=5000)
    goal: str = Field(default="hook", pattern="^(hook|shorten|pacing)$")
    seconds: int | None = Field(default=None, ge=10, le=180)
    tone: str = "standard"


@router.post("/ai/enhance", response_model=P.Enhanced)
def enhance(body: EnhanceReq, u: User = Depends(current_user), db: Session = Depends(get_db)):
    try:
        with _guard(db, u, COST["enhance"], "script enhance"):
            return P.enhance_script(db, body.script, body.goal, body.seconds, body.tone, u.id)
    except LLMError as e:
        raise HTTPException(503, str(e))


class ThumbReq(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    background_asset_id: str | None = None


@router.post("/tools/thumbnails")
def thumbnails(body: ThumbReq, u: User = Depends(current_user), db: Session = Depends(get_db)):
    from clue.render import thumbnail

    bg = None
    if body.background_asset_id:
        a = _own(db, Asset, body.background_asset_id, u, "Media")
        if a.kind != "image":
            raise HTTPException(422, "The background must be an image.")
        bg = storage.safe_path(a.path)
    batch, out = new_id(), []
    with _guard(db, u, COST["thumbnails"], "thumbnails"):
        for v in range(4):
            rel = f"{u.id}/thumbs/{batch}_{v}.png"
            dest = storage.root() / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(thumbnail.make(body.title, v, bg))
            out.append({"variant": v, "url": f"/api/files?path={rel}&t={storage.sign(rel, 1800)}"})
    return {"thumbnails": out, "size": "1280x720", "credits": COST["thumbnails"]}


class TtsReq(BaseModel):
    text: str = Field(min_length=2, max_length=5000)
    voice: str = "af_heart"
    speed: float = Field(default=1.0, ge=0.5, le=2.0)


def tts_cost(text: str) -> int:
    return max(1, math.ceil(len(text.split()) / 75))  # about 30 s of speech per credit


@router.post("/tools/voiceover")
def voiceover(body: TtsReq, u: User = Depends(current_user), db: Session = Depends(get_db)):
    return _enqueue(db, u, "voiceover", body.model_dump(), tts_cost(body.text), "voiceover")


@router.get("/voices/{voice_id}/preview")
def preview(voice_id: str, u: User = Depends(current_user)):
    """A short sample of a voice, generated once and cached on disk."""
    from clue.ai.tts import TTSError, get_tts

    if not voice_id.replace("_", "").isalnum():
        raise HTTPException(404, "Unknown voice.")
    f = get_settings().storage_dir / "voice_previews" / f"{voice_id}.wav"
    if not f.exists():
        try:
            get_tts().synthesize("Hi, I can narrate your next short video. Pick me, or try another voice.", voice_id, 1.0, f)
        except TTSError as e:
            raise HTTPException(503 if "Unknown" not in str(e) else 404, str(e))
    return FileResponse(f, media_type="audio/wav")
