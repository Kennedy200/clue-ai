"""Health, setup (OpenRouter key), dev inbox, plugins."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from clue.ai.llm import LLMError, OpenRouterProvider, get_provider
from clue.api.deps import current_user
from clue.core.config import get_settings
from clue.core.db import get_db
from clue.core.settings_store import get_setting, set_setting
from clue.models import DevMail, User
from clue.plugins.registry import discover

router = APIRouter(tags=["system"])


@router.get("/health")
def health(db: Session = Depends(get_db)):
    db.execute(text("select 1"))
    return {"ok": True, "mode": get_settings().app_mode}


@router.get("/setup/status")
def setup_status(db: Session = Depends(get_db)):
    has_key = bool(get_setting(db, "openrouter_api_key"))
    return {"has_key": has_key, "has_users": db.scalar(select(User.id).limit(1)) is not None, "mode": get_settings().app_mode}


class KeyBody(BaseModel):
    key: str


@router.post("/setup/key")
def save_key(body: KeyBody, db: Session = Depends(get_db)):
    """Validate against OpenRouter, then store encrypted. Open only until the first user exists."""
    if db.scalar(select(User.id).limit(1)) is not None:
        raise HTTPException(403, "Sign in as admin and use Admin > Settings to change the key.")
    return _save(body.key.strip(), db)


@router.post("/admin/key")
def admin_save_key(body: KeyBody, u: User = Depends(current_user), db: Session = Depends(get_db)):
    if not u.is_admin:
        raise HTTPException(403, "Admins only.")
    return _save(body.key.strip(), db)


def _save(key: str, db: Session) -> dict:
    if not key:
        raise HTTPException(400, "Paste your OpenRouter key first.")
    try:
        info = OpenRouterProvider(key).key_info()
    except LLMError as e:
        raise HTTPException(400, str(e))
    except Exception:
        raise HTTPException(502, "Could not reach OpenRouter. Check your internet connection.")
    set_setting(db, "openrouter_api_key", key)
    return {"ok": True, "info": _quota(info)}


def _quota(info: dict) -> dict:
    return {"label": info.get("label"), "usage": info.get("usage"), "limit": info.get("limit"), "is_free_tier": info.get("is_free_tier")}


@router.get("/ai/quota")
def quota(u: User = Depends(current_user), db: Session = Depends(get_db)):
    try:
        return {"ok": True, **_quota(get_provider(db).key_info())}  # type: ignore[attr-defined]
    except LLMError as e:
        return {"ok": False, "error": str(e)}
    except Exception:
        return {"ok": False, "error": "Could not reach OpenRouter."}


@router.get("/ai/models")
def models(u: User = Depends(current_user), db: Session = Depends(get_db)):
    try:
        return {"models": get_provider(db).list_models()}
    except LLMError as e:
        raise HTTPException(400, str(e))


@router.get("/dev-mail")
def dev_mail(db: Session = Depends(get_db)):
    """Local dev inbox. Disabled outside self_host mode."""
    if get_settings().app_mode != "self_host":
        raise HTTPException(404)
    rows = db.scalars(select(DevMail).order_by(DevMail.id.desc()).limit(100)).all()
    return [{"id": r.id, "to": r.to, "subject": r.subject, "body": r.body, "at": r.created_at.isoformat()} for r in rows]


@router.get("/plugins")
def plugins(u: User = Depends(current_user)):
    return discover()
