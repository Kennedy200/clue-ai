"""YouTube publishing (optional). Needs a Google OAuth client that the ADMIN creates; nothing is required from regular users.

Until an admin saves a client id/secret at Admin > Integrations this is simply "not configured" and the publish pack
(copy-paste title, description, hashtags + download) is the way to post. Tokens are stored encrypted per user.
"""
from __future__ import annotations

import json
from datetime import timedelta
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from clue.api.deps import admin_user, current_user
from clue.core import storage
from clue.core.config import get_settings
from clue.core.db import get_db
from clue.core.ids import new_id, utcnow
from clue.core.security import new_token
from clue.core.settings_store import get_setting, set_setting
from clue.jobs import queue
from clue.models import AuditLog, Project, ScheduledPost, Setting, User

router = APIRouter(tags=["youtube"])
SCOPE = "https://www.googleapis.com/auth/youtube.upload"
AUTH_URL, TOKEN_URL = "https://accounts.google.com/o/oauth2/v2/auth", "https://oauth2.googleapis.com/token"
UPLOAD_URL = "https://www.googleapis.com/upload/youtube/v3/videos"


def http() -> httpx.Client:  # a function so tests can swap in a mock transport
    return httpx.Client(timeout=60)


def configured(db: Session) -> bool:
    return bool(get_setting(db, "youtube_client_id") and get_setting(db, "youtube_client_secret"))


def redirect_uri() -> str:
    return f"{get_settings().site_url}/api/youtube/callback"


class Keys(BaseModel):
    client_id: str = Field(min_length=10, max_length=300)
    client_secret: str = Field(min_length=5, max_length=300)


@router.post("/admin/youtube")
def save_keys(body: Keys, a: User = Depends(admin_user), db: Session = Depends(get_db)):
    set_setting(db, "youtube_client_id", body.client_id.strip())
    set_setting(db, "youtube_client_secret", body.client_secret.strip())
    db.add(AuditLog(actor_id=a.id, action="youtube.configure", detail={}))
    db.commit()
    return {"ok": True, "redirect_uri": redirect_uri()}


@router.get("/youtube/status")
def status(u: User = Depends(current_user), db: Session = Depends(get_db)):
    return {"configured": configured(db), "connected": bool(get_setting(db, f"yt_token:{u.id}")), "redirect_uri": redirect_uri()}


@router.get("/youtube/auth-url")
def auth_url(u: User = Depends(current_user), db: Session = Depends(get_db)):
    if not configured(db):
        raise HTTPException(400, "YouTube publishing is not set up on this installation. Use the publish pack instead, or ask the admin.")
    state = new_token()
    set_setting(db, f"yt_state:{state}", f"{u.id}|{(utcnow() + timedelta(minutes=10)).isoformat()}")
    q = urlencode({"client_id": get_setting(db, "youtube_client_id"), "redirect_uri": redirect_uri(), "response_type": "code", "scope": SCOPE,
                   "access_type": "offline", "prompt": "consent", "state": state})
    return {"url": f"{AUTH_URL}?{q}"}


@router.get("/youtube/callback")
def callback(code: str = "", state: str = "", error: str = "", db: Session = Depends(get_db)):
    site = get_settings().site_url
    row = db.get(Setting, f"yt_state:{state}") if state else None
    if row is None:
        return RedirectResponse(f"{site}/app/calendar?yt=bad_state")
    uid, exp = get_setting(db, f"yt_state:{state}").split("|")
    db.delete(row)
    db.commit()
    if error or not code or exp < utcnow().isoformat():
        return RedirectResponse(f"{site}/app/calendar?yt=denied")
    with http() as c:
        r = c.post(TOKEN_URL, data={"code": code, "client_id": get_setting(db, "youtube_client_id"), "client_secret": get_setting(db, "youtube_client_secret"),
                                    "redirect_uri": redirect_uri(), "grant_type": "authorization_code"})
    if r.status_code != 200 or "refresh_token" not in r.json():
        return RedirectResponse(f"{site}/app/calendar?yt=failed")
    d = r.json()
    set_setting(db, f"yt_token:{uid}", json.dumps({"refresh_token": d["refresh_token"]}))
    return RedirectResponse(f"{site}/app/calendar?yt=connected")


@router.post("/youtube/disconnect")
def disconnect(u: User = Depends(current_user), db: Session = Depends(get_db)):
    row = db.get(Setting, f"yt_token:{u.id}")
    if row:
        db.delete(row)
        db.commit()
    return {"ok": True}


class PublishBody(BaseModel):
    project_id: str
    title: str = Field(min_length=1, max_length=100)
    description: str = Field(default="", max_length=4900)
    privacy: str = Field(default="private", pattern="^(private|unlisted|public)$")
    post_id: str | None = None


@router.post("/youtube/publish")
def publish(body: PublishBody, u: User = Depends(current_user), db: Session = Depends(get_db)):
    if not configured(db) or not get_setting(db, f"yt_token:{u.id}"):
        raise HTTPException(400, "Connect your YouTube channel first.")
    p = db.get(Project, body.project_id)
    if p is None or p.user_id != u.id or not p.output_path:
        raise HTTPException(404, "Finish this video first.")
    job = queue.enqueue(db, "youtube_publish", {"project_id": p.id, "title": body.title, "description": body.description, "privacy": body.privacy, "post_id": body.post_id}, user_id=u.id)
    return {"job_id": job.id}


def upload(db: Session, user_id: str, project: Project, title: str, description: str, privacy: str) -> str:
    """Refresh the access token, then do a resumable upload. Returns the video URL."""
    tok = json.loads(get_setting(db, f"yt_token:{user_id}"))
    with http() as c:
        r = c.post(TOKEN_URL, data={"client_id": get_setting(db, "youtube_client_id"), "client_secret": get_setting(db, "youtube_client_secret"),
                                    "refresh_token": tok["refresh_token"], "grant_type": "refresh_token"})
        if r.status_code != 200:
            raise RuntimeError("YouTube sign-in expired. Reconnect your channel.")
        access = r.json()["access_token"]
        path = storage.root() / project.output_path
        meta = {"snippet": {"title": title, "description": description, "categoryId": "22"}, "status": {"privacyStatus": privacy, "selfDeclaredMadeForKids": False}}
        init = c.post(f"{UPLOAD_URL}?uploadType=resumable&part=snippet,status", json=meta,
                      headers={"Authorization": f"Bearer {access}", "X-Upload-Content-Type": "video/mp4", "X-Upload-Content-Length": str(path.stat().st_size)})
        if init.status_code != 200 or "location" not in init.headers:
            raise RuntimeError(f"YouTube refused the upload ({init.status_code}).")
        up = c.put(init.headers["location"], content=path.read_bytes(), headers={"Content-Type": "video/mp4"}, timeout=1800)
        if up.status_code not in (200, 201):
            raise RuntimeError(f"YouTube upload failed ({up.status_code}).")
        return f"https://youtu.be/{up.json()['id']}"
