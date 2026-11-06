"""AI endpoints: script planning (one LLM call)."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from clue.ai.llm import LLMError
from clue.ai.prompts.plan import NICHES, STYLES, TONES, VideoPlan, plan_video
from clue.api.deps import current_user
from clue.core.db import get_db
from clue.models import User

router = APIRouter(prefix="/ai", tags=["ai"])


class PlanReq(BaseModel):
    idea: str = Field(min_length=3, max_length=4000)
    style: str = "explainer"
    tone: str = "standard"
    niche: str = "general"
    seconds: int = Field(default=45, ge=10, le=180)


@router.get("/options")
def options():
    return {"styles": list(STYLES), "tones": list(TONES), "niches": NICHES}


@router.post("/plan", response_model=VideoPlan)
def plan(body: PlanReq, u: User = Depends(current_user), db: Session = Depends(get_db)):
    if body.style not in STYLES:
        raise HTTPException(422, "Unknown style.")
    try:
        return plan_video(db, body.idea, style=body.style, tone=body.tone, niche=body.niche, seconds=body.seconds, user_id=u.id)
    except LLMError as e:
        raise HTTPException(503, str(e))
