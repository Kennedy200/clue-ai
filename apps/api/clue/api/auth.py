"""Auth: signup, login, logout, verify email, forgot/reset password, change password, delete, export."""
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from clue.api.deps import COOKIE, current_user
from clue.core import credits
from clue.core.config import get_settings
from clue.core.db import get_db
from clue.core.ids import utcnow
from clue.core.mail import send_mail
from clue.core.ratelimit import limit
from clue.core.security import hash_password, new_token, sha256, verify_password
from clue.models import AuditLog, CreditLedger, EmailToken, Plan, User
from clue.models import Session as SessionRow

router = APIRouter(prefix="/auth", tags=["auth"])
SESSION_DAYS = 30
SELF_HOST_CREDITS = 1_000_000


class Signup(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    name: str = Field(default="", max_length=120)
    referral_code: str | None = None


class Login(BaseModel):
    email: EmailStr
    password: str


def _public(u: User, db: Session) -> dict:
    return {
        "id": u.id, "email": u.email, "name": u.name, "is_admin": u.is_admin,
        "email_verified": u.email_verified, "plan_id": u.plan_id,
        "credits": credits.balance(db, u.id), "referral_code": u.referral_code,
        "prefs": u.prefs, "mode": get_settings().app_mode,
    }


def _issue_token(db: Session, u: User, kind: str, hours: int) -> str:
    raw = new_token()
    db.add(EmailToken(user_id=u.id, kind=kind, token_hash=sha256(raw), expires_at=utcnow() + timedelta(hours=hours)))
    db.commit()
    return raw


def _start_session(db: Session, u: User, response: Response) -> None:
    raw = new_token()
    db.add(SessionRow(user_id=u.id, token_hash=sha256(raw), csrf=new_token(), expires_at=utcnow() + timedelta(days=SESSION_DAYS)))
    db.commit()
    secure = get_settings().site_url.startswith("https")
    response.set_cookie(COOKIE, raw, httponly=True, samesite="lax", secure=secure, max_age=SESSION_DAYS * 86400, path="/")


@router.post("/signup", dependencies=[Depends(limit("signup", 5, 60))])
def signup(body: Signup, response: Response, db: Session = Depends(get_db)):
    s = get_settings()
    email = body.email.lower()
    if db.scalar(select(User.id).where(User.email == email)):
        raise HTTPException(409, "That email already has an account. Try signing in.")
    u = User(email=email, password_hash=hash_password(body.password), name=body.name.strip())
    if email == s.admin_email.lower():
        u.is_admin = True
    ref = db.scalar(select(User).where(User.referral_code == body.referral_code)) if body.referral_code else None
    if ref:
        u.referred_by = ref.id
    db.add(u)
    db.commit()
    plan = db.get(Plan, "free")
    grant = SELF_HOST_CREDITS if s.app_mode == "self_host" else (plan.monthly_credits if plan else 15)
    credits.grant(db, u.id, grant, "signup grant")
    if ref and s.app_mode == "saas":
        credits.grant(db, u.id, 10, "referral bonus", ref_id=f"ref:{u.id}")
        credits.grant(db, ref.id, 10, "referral reward", ref_id=f"refr:{u.id}")
    tok = _issue_token(db, u, "verify", 48)
    send_mail(db, u.email, "Verify your Clue AI email", f"Welcome to Clue AI!\n\nVerify your email: {s.site_url}/verify?token={tok}")
    _start_session(db, u, response)
    return _public(u, db)


@router.post("/login", dependencies=[Depends(limit("login", 5, 60))])
def login(body: Login, response: Response, db: Session = Depends(get_db)):
    u = db.scalar(select(User).where(User.email == body.email.lower()))
    bad = HTTPException(401, "Wrong email or password.")
    if u is None or u.deleted_at:
        raise bad
    if u.locked_until and u.locked_until > utcnow():
        raise HTTPException(429, "Too many failed attempts. Try again in a few minutes.")
    if not verify_password(u.password_hash, body.password):
        u.failed_logins += 1
        if u.failed_logins >= 5:
            u.locked_until = utcnow() + timedelta(minutes=min(60, 2 ** (u.failed_logins - 4)))
        db.commit()
        raise bad
    if u.is_suspended:
        raise HTTPException(403, "This account is suspended. Contact support.")
    u.failed_logins, u.locked_until = 0, None
    db.commit()
    _start_session(db, u, response)
    return _public(u, db)


@router.post("/logout")
def logout(request: Request, response: Response, u: User = Depends(current_user), db: Session = Depends(get_db)):
    tok = request.cookies.get(COOKIE)
    if tok:
        row = db.scalar(select(SessionRow).where(SessionRow.token_hash == sha256(tok)))
        if row:
            db.delete(row)
            db.commit()
    response.delete_cookie(COOKIE, path="/")
    return {"ok": True}


@router.get("/me")
def me(request: Request, u: User = Depends(current_user), db: Session = Depends(get_db)):
    row = db.scalar(select(SessionRow).where(SessionRow.token_hash == sha256(request.cookies[COOKIE])))
    return {**_public(u, db), "csrf": row.csrf}


def _consume(db: Session, raw: str, kind: str) -> User:
    t = db.scalar(select(EmailToken).where(EmailToken.token_hash == sha256(raw), EmailToken.kind == kind))
    if t is None or t.used or t.expires_at < utcnow():
        raise HTTPException(400, "This link is invalid or has expired. Request a new one.")
    t.used = True
    db.commit()
    return db.get(User, t.user_id)


class TokenBody(BaseModel):
    token: str


@router.post("/verify")
def verify(body: TokenBody, db: Session = Depends(get_db)):
    u = _consume(db, body.token, "verify")
    u.email_verified = True
    db.commit()
    return {"ok": True}


class Email(BaseModel):
    email: EmailStr


@router.post("/forgot", dependencies=[Depends(limit("forgot", 5, 60))])
def forgot(body: Email, db: Session = Depends(get_db)):
    u = db.scalar(select(User).where(User.email == body.email.lower()))
    if u and not u.deleted_at:
        tok = _issue_token(db, u, "reset", 1)
        send_mail(db, u.email, "Reset your Clue AI password", f"Reset your password: {get_settings().site_url}/reset?token={tok}\n\nIgnore this if it wasn't you.")
    return {"ok": True}  # same answer either way: no account enumeration


class Reset(BaseModel):
    token: str
    password: str = Field(min_length=8, max_length=128)


@router.post("/reset", dependencies=[Depends(limit("reset", 5, 60))])
def reset(body: Reset, db: Session = Depends(get_db)):
    u = _consume(db, body.token, "reset")
    u.password_hash = hash_password(body.password)
    u.failed_logins, u.locked_until = 0, None
    for s in db.scalars(select(SessionRow).where(SessionRow.user_id == u.id)).all():
        db.delete(s)
    db.commit()
    return {"ok": True}


class ChangePw(BaseModel):
    current: str
    new: str = Field(min_length=8, max_length=128)


@router.post("/change-password")
def change_password(body: ChangePw, u: User = Depends(current_user), db: Session = Depends(get_db)):
    if not verify_password(u.password_hash, body.current):
        raise HTTPException(400, "Current password is wrong.")
    u.password_hash = hash_password(body.new)
    db.commit()
    return {"ok": True}


class DeleteBody(BaseModel):
    password: str


@router.post("/delete-account")
def delete_account(body: DeleteBody, response: Response, u: User = Depends(current_user), db: Session = Depends(get_db)):
    if not verify_password(u.password_hash, body.password):
        raise HTTPException(400, "Password is wrong.")
    db.add(AuditLog(actor_id=u.id, action="account.delete", detail={}))
    db.delete(u)  # sessions, tokens, ledger cascade
    db.commit()
    response.delete_cookie(COOKIE, path="/")
    return {"ok": True}


@router.get("/export")
def export_data(u: User = Depends(current_user), db: Session = Depends(get_db)):
    ledger = db.scalars(select(CreditLedger).where(CreditLedger.user_id == u.id)).all()
    return {
        "user": {"id": u.id, "email": u.email, "name": u.name, "created_at": u.created_at.isoformat(), "prefs": u.prefs},
        "credit_ledger": [{"delta": r.delta, "kind": r.kind, "reason": r.reason, "at": r.created_at.isoformat()} for r in ledger],
    }
