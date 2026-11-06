"""Workspace features: teams and roles, brand kits, bulk CSV creation, content calendar, analytics, publish pack."""
from __future__ import annotations

import csv
import io
import re
from collections import Counter
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from clue.api.deps import current_user
from clue.api.render import RENDER_COST, TextStory, create_text_story
from clue.core import credits, storage
from clue.core.config import get_settings
from clue.core.db import get_db
from clue.core.ids import new_id, utcnow
from clue.core.mail import send_mail
from clue.core.security import new_token, sha256
from clue.models import (BrandKit, CreditLedger, Invoice, Plan, Project, ProjectVersion, ScheduledPost, SharedProject, Team,
                         TeamInvite, TeamMember, User)
from clue.render.scene import CaptionStyle

router = APIRouter(tags=["workspace"])
RANK = {"viewer": 1, "editor": 2, "admin": 3, "owner": 4}
MAX_SEATS = 10
MAX_BULK = 25


def _feature(u: User, db: Session, name: str) -> None:
    if get_settings().app_mode == "self_host":
        return
    plan = db.get(Plan, u.plan_id)
    if not (plan and plan.features.get(name)):
        raise HTTPException(403, "This feature is not included in your plan. Upgrade on the Billing page.")


def _role(db: Session, u: User, team_id: str) -> str | None:
    m = db.scalar(select(TeamMember).where(TeamMember.team_id == team_id, TeamMember.user_id == u.id))
    return m.role if m else None


def _need(db: Session, u: User, team_id: str, minimum: str) -> str:
    r = _role(db, u, team_id)
    if r is None:
        raise HTTPException(404, "Team not found.")  # do not reveal teams the user is not in
    if RANK[r] < RANK[minimum]:
        raise HTTPException(403, f"You need the {minimum} role for this. You are {r}.")
    return r


# ---------------- teams ----------------
class TeamBody(BaseModel):
    name: str = Field(min_length=2, max_length=80)


@router.get("/teams")
def my_teams(u: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.execute(select(Team, TeamMember.role).join(TeamMember, TeamMember.team_id == Team.id).where(TeamMember.user_id == u.id)).all()
    return [{"id": t.id, "name": t.name, "role": r} for t, r in rows]


@router.post("/teams")
def create_team(body: TeamBody, u: User = Depends(current_user), db: Session = Depends(get_db)):
    _feature(u, db, "team")
    if (db.scalar(select(func.count()).select_from(Team).where(Team.owner_id == u.id)) or 0) >= 3:
        raise HTTPException(400, "You can own up to 3 teams.")
    t = Team(name=body.name.strip(), owner_id=u.id)
    db.add(t)
    db.flush()
    db.add(TeamMember(team_id=t.id, user_id=u.id, role="owner"))
    db.commit()
    return {"id": t.id, "name": t.name, "role": "owner"}


@router.get("/teams/{tid}")
def team_detail(tid: str, u: User = Depends(current_user), db: Session = Depends(get_db)):
    role = _need(db, u, tid, "viewer")
    t = db.get(Team, tid)
    members = db.execute(select(TeamMember, User).join(User, User.id == TeamMember.user_id).where(TeamMember.team_id == tid).order_by(TeamMember.created_at)).all()
    invites = db.scalars(select(TeamInvite).where(TeamInvite.team_id == tid, TeamInvite.used == False, TeamInvite.expires_at > utcnow())).all()  # noqa: E712
    return {"id": t.id, "name": t.name, "role": role,
            "members": [{"user_id": m.user_id, "email": usr.email, "name": usr.name, "role": m.role} for m, usr in members],
            "invites": [{"id": i.id, "email": i.email, "role": i.role} for i in invites] if RANK[role] >= RANK["admin"] else []}


class InviteBody(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    role: str = Field(default="viewer", pattern="^(admin|editor|viewer)$")


@router.post("/teams/{tid}/invite")
def invite(tid: str, body: InviteBody, u: User = Depends(current_user), db: Session = Depends(get_db)):
    my = _need(db, u, tid, "admin")
    if body.role == "admin" and my != "owner":
        raise HTTPException(403, "Only the owner can invite admins.")
    email = body.email.strip().lower()
    if "@" not in email:
        raise HTTPException(422, "Enter a valid email address.")
    seats = (db.scalar(select(func.count()).select_from(TeamMember).where(TeamMember.team_id == tid)) or 0) + \
            (db.scalar(select(func.count()).select_from(TeamInvite).where(TeamInvite.team_id == tid, TeamInvite.used == False, TeamInvite.expires_at > utcnow())) or 0)  # noqa: E712
    if seats >= MAX_SEATS:
        raise HTTPException(400, f"A team can have up to {MAX_SEATS} people including pending invites.")
    existing = db.scalar(select(User).where(User.email == email))
    if existing and _role(db, existing, tid):
        raise HTTPException(400, "That person is already in the team.")
    tok = new_token()
    db.add(TeamInvite(team_id=tid, email=email, role=body.role, token_hash=sha256(tok), expires_at=utcnow() + timedelta(days=7)))
    db.commit()
    team = db.get(Team, tid)
    send_mail(db, email, f"{u.name or u.email} invited you to {team.name} on Clue AI",
              f"Accept the invite (valid 7 days): {get_settings().site_url}/app/team?invite={tok}\n\nYou will join as {body.role}. You need an account with this email address.")
    return {"ok": True}


class AcceptBody(BaseModel):
    token: str = Field(min_length=10, max_length=200)


@router.post("/teams/accept")
def accept(body: AcceptBody, u: User = Depends(current_user), db: Session = Depends(get_db)):
    inv = db.scalar(select(TeamInvite).where(TeamInvite.token_hash == sha256(body.token)))
    if inv is None or inv.used or inv.expires_at < utcnow():
        raise HTTPException(400, "This invite is invalid or has expired. Ask for a new one.")
    if inv.email != u.email.lower():
        raise HTTPException(403, f"This invite was sent to {inv.email}. Sign in with that email to accept it.")
    if not _role(db, u, inv.team_id):
        db.add(TeamMember(team_id=inv.team_id, user_id=u.id, role=inv.role))
    inv.used = True
    db.commit()
    return {"ok": True, "team_id": inv.team_id}


class RoleBody(BaseModel):
    role: str = Field(pattern="^(admin|editor|viewer)$")


@router.put("/teams/{tid}/members/{uid}")
def set_role(tid: str, uid: str, body: RoleBody, u: User = Depends(current_user), db: Session = Depends(get_db)):
    my = _need(db, u, tid, "admin")
    m = db.scalar(select(TeamMember).where(TeamMember.team_id == tid, TeamMember.user_id == uid))
    if m is None:
        raise HTTPException(404, "Member not found.")
    if m.role == "owner":
        raise HTTPException(400, "The owner's role cannot change.")
    if my != "owner" and (body.role == "admin" or m.role == "admin"):
        raise HTTPException(403, "Only the owner can add or change admins.")
    m.role = body.role
    db.commit()
    return {"ok": True}


@router.delete("/teams/{tid}/members/{uid}")
def remove_member(tid: str, uid: str, u: User = Depends(current_user), db: Session = Depends(get_db)):
    my = _need(db, u, tid, "viewer")
    m = db.scalar(select(TeamMember).where(TeamMember.team_id == tid, TeamMember.user_id == uid))
    if m is None:
        raise HTTPException(404, "Member not found.")
    if m.role == "owner":
        raise HTTPException(400, "The owner cannot leave. Delete the team instead.")
    if uid != u.id:
        if RANK[my] < RANK["admin"]:
            raise HTTPException(403, "You need the admin role to remove people.")
        if m.role == "admin" and my != "owner":
            raise HTTPException(403, "Only the owner can remove admins.")
    db.delete(m)
    db.commit()
    return {"ok": True}


@router.delete("/teams/{tid}")
def delete_team(tid: str, u: User = Depends(current_user), db: Session = Depends(get_db)):
    _need(db, u, tid, "owner")
    db.delete(db.get(Team, tid))
    db.commit()
    return {"ok": True}


class ShareBody(BaseModel):
    project_id: str


@router.post("/teams/{tid}/share")
def share(tid: str, body: ShareBody, u: User = Depends(current_user), db: Session = Depends(get_db)):
    _need(db, u, tid, "editor")
    p = db.get(Project, body.project_id)
    if p is None or p.user_id != u.id or not p.output_path:
        raise HTTPException(404, "Finish a video first, then share it.")
    if not db.scalar(select(SharedProject.id).where(SharedProject.team_id == tid, SharedProject.project_id == p.id)):
        db.add(SharedProject(team_id=tid, project_id=p.id, shared_by=u.id))
        db.commit()
    return {"ok": True}


@router.delete("/teams/{tid}/share/{pid}")
def unshare(tid: str, pid: str, u: User = Depends(current_user), db: Session = Depends(get_db)):
    my = _need(db, u, tid, "editor")
    s = db.scalar(select(SharedProject).where(SharedProject.team_id == tid, SharedProject.project_id == pid))
    if s is None:
        raise HTTPException(404, "Not shared.")
    if s.shared_by != u.id and RANK[my] < RANK["admin"]:
        raise HTTPException(403, "Only the person who shared it, or an admin, can remove it.")
    db.delete(s)
    db.commit()
    return {"ok": True}


@router.get("/teams/{tid}/videos")
def team_videos(tid: str, u: User = Depends(current_user), db: Session = Depends(get_db)):
    _need(db, u, tid, "viewer")
    rows = db.execute(select(SharedProject, Project, User).join(Project, Project.id == SharedProject.project_id).join(User, User.id == SharedProject.shared_by)
                      .where(SharedProject.team_id == tid).order_by(SharedProject.created_at.desc()).limit(100)).all()
    return [{"project_id": p.id, "title": p.title, "style": p.style, "by": usr.name or usr.email, "shared_at": s.created_at.isoformat(),
             "url": f"/api/files?path={p.output_path}&t={storage.sign(p.output_path, 900)}" if p.output_path else None} for s, p, usr in rows]


# ---------------- brand kits ----------------
class KitBody(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    caption: CaptionStyle = CaptionStyle()
    watermark: str = Field(default="", max_length=60)
    outro: str = Field(default="", max_length=120)
    team_id: str | None = None
    is_default: bool = False


def _kit_view(k: BrandKit) -> dict:
    return {"id": k.id, "name": k.name, "caption": k.caption, "watermark": k.watermark, "outro": k.outro, "team_id": k.team_id, "is_default": k.is_default, "owner_id": k.user_id}


def _kit_access(db: Session, u: User, k: BrandKit, minimum: str) -> None:
    if k.team_id:
        _need(db, u, k.team_id, minimum)
    elif k.user_id != u.id:
        raise HTTPException(404, "Brand kit not found.")


@router.get("/brand-kits")
def kits(u: User = Depends(current_user), db: Session = Depends(get_db)):
    team_ids = [r for (r,) in db.execute(select(TeamMember.team_id).where(TeamMember.user_id == u.id))]
    rows = db.scalars(select(BrandKit).where((BrandKit.user_id == u.id) | (BrandKit.team_id.in_(team_ids))).order_by(BrandKit.created_at)).all()
    return [_kit_view(k) for k in rows]


@router.post("/brand-kits")
def create_kit(body: KitBody, u: User = Depends(current_user), db: Session = Depends(get_db)):
    _feature(u, db, "brand_kit") if not body.team_id else _feature(u, db, "team")
    if body.team_id:
        _need(db, u, body.team_id, "editor")
    n = db.scalar(select(func.count()).select_from(BrandKit).where(BrandKit.user_id == u.id)) or 0
    if n >= 20:
        raise HTTPException(400, "You can keep up to 20 brand kits.")
    k = BrandKit(user_id=u.id, team_id=body.team_id, name=body.name.strip(), caption=body.caption.model_dump(), watermark=body.watermark, outro=body.outro, is_default=False)
    db.add(k)
    db.commit()
    if body.is_default:
        _make_default(db, u, k)
    return _kit_view(k)


def _make_default(db: Session, u: User, k: BrandKit) -> None:
    for o in db.scalars(select(BrandKit).where(BrandKit.user_id == u.id, BrandKit.team_id == k.team_id)):
        o.is_default = o.id == k.id
    db.commit()


@router.put("/brand-kits/{kid}")
def update_kit(kid: str, body: KitBody, u: User = Depends(current_user), db: Session = Depends(get_db)):
    k = db.get(BrandKit, kid)
    if k is None:
        raise HTTPException(404, "Brand kit not found.")
    _kit_access(db, u, k, "editor")
    k.name, k.caption, k.watermark, k.outro = body.name.strip(), body.caption.model_dump(), body.watermark, body.outro
    db.commit()
    if body.is_default:
        _make_default(db, u, k)
    return _kit_view(k)


@router.delete("/brand-kits/{kid}")
def delete_kit(kid: str, u: User = Depends(current_user), db: Session = Depends(get_db)):
    k = db.get(BrandKit, kid)
    if k is None:
        raise HTTPException(404, "Brand kit not found.")
    _kit_access(db, u, k, "admin")
    db.delete(k)
    db.commit()
    return {"ok": True}


class ApplyBody(BaseModel):
    kit_id: str


@router.post("/projects/{pid}/apply-brand")
def apply_brand(pid: str, body: ApplyBody, u: User = Depends(current_user), db: Session = Depends(get_db)):
    p = db.get(Project, pid)
    if p is None or p.user_id != u.id or not p.scene_json:
        raise HTTPException(404, "Video not found.")
    if p.status == "rendering":
        raise HTTPException(409, "This video is rendering. Wait for it to finish.")
    k = db.get(BrandKit, body.kit_id)
    if k is None:
        raise HTTPException(404, "Brand kit not found.")
    _kit_access(db, u, k, "viewer")
    db.add(ProjectVersion(project_id=p.id, version=p.version, scene_json=p.scene_json))
    p.scene_json = {**p.scene_json, "captions": {**p.scene_json.get("captions", {}), **k.caption}}
    p.version += 1
    db.commit()
    return {"version": p.version}


# ---------------- bulk CSV ----------------
TEMPLATE = "title,text\nMy first story,Stop scrolling. Here is one trick that saves you an hour a day. Try it today and tell me how it goes.\n"


@router.get("/bulk/template")
def bulk_template(u: User = Depends(current_user)):
    return {"csv": TEMPLATE, "max_rows": MAX_BULK}


class BulkBody(BaseModel):
    csv: str = Field(min_length=5, max_length=300_000)
    brand_kit_id: str | None = None
    voice: str = "af_heart"


def parse_bulk(text: str) -> tuple[list[dict], list[dict]]:
    """Returns (valid rows, row errors). Accepts title,text (or script) columns, comma or semicolon."""
    text = text.lstrip("﻿")
    try:
        dialect = csv.Sniffer().sniff(text[:2000], delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    rd = csv.DictReader(io.StringIO(text), dialect=dialect)
    cols = {(c or "").strip().lower(): c for c in (rd.fieldnames or [])}
    tcol = cols.get("text") or cols.get("script")
    if not tcol:
        return [], [{"row": 1, "error": "Missing a 'text' column. Download the template to see the format."}]
    rows, errs = [], []
    for i, r in enumerate(rd, start=2):
        t = (r.get(tcol) or "").strip()
        title = (r.get(cols.get("title", "")) or "").strip() if cols.get("title") else ""
        if not t and not title:
            continue
        if len(t) < 5:
            errs.append({"row": i, "error": "The text is too short (5 characters minimum)."})
        elif len(t) > 6000:
            errs.append({"row": i, "error": "The text is longer than 6000 characters."})
        else:
            rows.append({"row": i, "title": title[:200] or f"Story {len(rows) + 1}", "text": t})
    return rows, errs


@router.post("/bulk/text-stories")
def bulk_create(body: BulkBody, u: User = Depends(current_user), db: Session = Depends(get_db)):
    _feature(u, db, "bulk")
    rows, errs = parse_bulk(body.csv)
    if errs:
        raise HTTPException(422, "; ".join(f"row {e['row']}: {e['error']}" for e in errs[:5]))
    if not rows:
        raise HTTPException(422, "No rows found in the CSV.")
    if len(rows) > MAX_BULK:
        raise HTTPException(422, f"Up to {MAX_BULK} videos per batch. Your file has {len(rows)}.")
    need = RENDER_COST["fast"] * len(rows)
    have = credits.balance(db, u.id)
    if have < need:
        raise HTTPException(402, f"Not enough credits. {len(rows)} videos cost {need}; you have {have}.")
    cap = CaptionStyle()
    if body.brand_kit_id:
        k = db.get(BrandKit, body.brand_kit_id)
        if k is None:
            raise HTTPException(404, "Brand kit not found.")
        _kit_access(db, u, k, "viewer")
        cap = CaptionStyle.model_validate({**cap.model_dump(), **k.caption})
    out = []
    for r in rows:
        try:
            res = create_text_story(TextStory(title=r["title"], text=r["text"], voice=body.voice, caption=cap), u, db)
            out.append({"row": r["row"], "title": r["title"], **res})
        except HTTPException as e:
            out.append({"row": r["row"], "title": r["title"], "error": str(e.detail)})
    return {"created": sum(1 for o in out if "job_id" in o), "results": out}


# ---------------- calendar ----------------
class PostBody(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    scheduled_at: datetime
    platform: str = Field(default="youtube", pattern="^(youtube|tiktok|instagram|facebook|x|other)$")
    project_id: str | None = None
    notes: str = Field(default="", max_length=2000)
    status: str = Field(default="planned", pattern="^(planned|published|skipped)$")


def _post_view(s: ScheduledPost) -> dict:
    return {"id": s.id, "title": s.title, "scheduled_at": s.scheduled_at.isoformat(), "platform": s.platform, "project_id": s.project_id,
            "notes": s.notes, "status": s.status, "external_url": s.external_url}


def _own_post(db: Session, u: User, pid: str) -> ScheduledPost:
    s = db.get(ScheduledPost, pid)
    if s is None or s.user_id != u.id:
        raise HTTPException(404, "Post not found.")
    return s


def _check_project(db: Session, u: User, pid: str | None) -> None:
    if pid:
        p = db.get(Project, pid)
        if p is None or p.user_id != u.id:
            raise HTTPException(404, "Video not found.")


def _naive_utc(dt: datetime) -> datetime:
    return dt.astimezone(timezone.utc).replace(tzinfo=None) if dt.tzinfo else dt


@router.get("/calendar")
def calendar(u: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(ScheduledPost).where(ScheduledPost.user_id == u.id).order_by(ScheduledPost.scheduled_at).limit(500)).all()
    return [_post_view(s) for s in rows]


@router.post("/calendar")
def add_post(body: PostBody, u: User = Depends(current_user), db: Session = Depends(get_db)):
    _check_project(db, u, body.project_id)
    s = ScheduledPost(user_id=u.id, title=body.title.strip(), scheduled_at=_naive_utc(body.scheduled_at), platform=body.platform,
                      project_id=body.project_id, notes=body.notes, status=body.status)
    db.add(s)
    db.commit()
    return _post_view(s)


@router.put("/calendar/{pid}")
def edit_post(pid: str, body: PostBody, u: User = Depends(current_user), db: Session = Depends(get_db)):
    s = _own_post(db, u, pid)
    _check_project(db, u, body.project_id)
    s.title, s.scheduled_at, s.platform, s.project_id, s.notes, s.status = body.title.strip(), _naive_utc(body.scheduled_at), body.platform, body.project_id, body.notes, body.status
    db.commit()
    return _post_view(s)


@router.delete("/calendar/{pid}")
def del_post(pid: str, u: User = Depends(current_user), db: Session = Depends(get_db)):
    db.delete(_own_post(db, u, pid))
    db.commit()
    return {"ok": True}


# ---------------- publish pack ----------------
STOP = set("the a an and or but of to in on for with is are was were it this that you your i we they at by be as from have has not no can will just so if then than".split())


@router.get("/projects/{pid}/publish-pack")
def publish_pack(pid: str, u: User = Depends(current_user), db: Session = Depends(get_db)):
    """Title, description and hashtags to paste when posting by hand (works on every platform, no account linking)."""
    p = db.get(Project, pid)
    if p is None or p.user_id != u.id or not p.output_path:
        raise HTTPException(404, "Finish this video first.")
    text = " ".join(s.get("text", "") for s in (p.scene_json or {}).get("scenes", []))
    words = [w for w in re.findall(r"[a-z]{4,}", text.lower()) if w not in STOP]
    tags = [f"#{w}" for w, _ in Counter(words).most_common(5)] + ["#shorts"]
    desc = (text[:300].rsplit(" ", 1)[0] + "…") if len(text) > 300 else text
    return {"title": p.title[:100], "description": f"{desc}\n\n{' '.join(tags)}\n\nMade with Clue AI", "hashtags": tags,
            "download_url": f"/api/files?path={p.output_path}&t={storage.sign(p.output_path, 900)}"}


# ---------------- analytics ----------------
@router.get("/analytics")
def analytics(u: User = Depends(current_user), db: Session = Depends(get_db)):
    since = utcnow() - timedelta(days=30)
    projs = db.scalars(select(Project).where(Project.user_id == u.id)).all()
    by_style = Counter(p.style for p in projs)
    by_status = Counter(p.status for p in projs)
    secs = sum((p.duration or 0) for p in projs if p.status == "done") / 1000
    spend = {}
    for led in db.scalars(select(CreditLedger).where(CreditLedger.user_id == u.id, CreditLedger.kind == "reserve", CreditLedger.created_at >= since)):
        d = led.created_at.date().isoformat()
        spend[d] = spend.get(d, 0) + (-led.delta)
    refunded = {r.ref_id for r in db.scalars(select(CreditLedger).where(CreditLedger.user_id == u.id, CreditLedger.kind == "refund"))}
    posts = db.scalars(select(ScheduledPost).where(ScheduledPost.user_id == u.id)).all()
    return {"videos": len(projs), "by_status": dict(by_status), "by_style": dict(by_style), "minutes_made": round(secs / 60, 1),
            "credits_spent_30d": sum(spend.values()), "spend_by_day": [{"date": k, "credits": v} for k, v in sorted(spend.items())],
            "posts": {"planned": sum(1 for s in posts if s.status == "planned"), "published": sum(1 for s in posts if s.status == "published")},
            "refunded_jobs": len(refunded)}
