"""Shared request dependencies: DB session, current user, CSRF."""
from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from clue.core.db import get_db
from clue.core.ids import utcnow
from clue.core.security import sha256
from clue.models import Session as SessionRow
from clue.models import User

COOKIE = "clue_session"
SAFE = {"GET", "HEAD", "OPTIONS"}


def get_session(request: Request, db: Session = Depends(get_db)) -> SessionRow | None:
    tok = request.cookies.get(COOKIE)
    if not tok:
        return None
    s = db.scalar(select(SessionRow).where(SessionRow.token_hash == sha256(tok)))
    if s is None or s.expires_at < utcnow():
        return None
    return s


def current_user(request: Request, s: SessionRow | None = Depends(get_session), db: Session = Depends(get_db)) -> User:
    if s is None:
        raise HTTPException(401, "Please sign in.")
    if request.method not in SAFE and request.headers.get("x-csrf-token") != s.csrf:
        raise HTTPException(403, "Security check failed. Refresh the page and try again.")
    u = db.get(User, s.user_id)
    if u is None or u.deleted_at or u.is_suspended:
        raise HTTPException(401, "Please sign in.")
    return u


def admin_user(u: User = Depends(current_user)) -> User:
    if not u.is_admin:
        raise HTTPException(403, "Admins only.")
    return u
