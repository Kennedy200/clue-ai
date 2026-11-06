"""Reference data (plans) and demo data (`python -m clue.seed`)."""
import secrets

from sqlalchemy import select
from sqlalchemy.orm import Session

from clue.core import credits
from clue.core.config import get_settings
from clue.core.db import SessionLocal
from clue.core.security import hash_password
from clue.models import Plan, User

PLANS = [
    # id, name, NGN/month, USD cents/month, credits
    ("free", "Free", 0, 0, 15, {"watermark": True, "modes": ["fast"], "brand_kit": False}),
    ("starter", "Starter", 9900, 700, 200, {"watermark": False, "modes": ["fast"], "max_seconds": 60}),
    ("creator", "Creator", 19900, 1400, 500, {"watermark": False, "modes": ["fast", "pro", "cinematic"], "brand_kit": True}),
    ("business", "Business", 49900, 3500, 1200, {"watermark": False, "modes": ["fast", "pro", "cinematic"], "brand_kit": True, "team": True, "bulk": True}),
]


def ensure_reference_data(db: Session) -> None:
    """Idempotent: create plans that do not exist yet (admins may edit them afterwards)."""
    for i, (pid, name, ngn, usd, cr, feats) in enumerate(PLANS):
        row = db.get(Plan, pid)
        if row is None:
            db.add(Plan(id=pid, name=name, price_ngn_month=ngn, price_usd_month=usd, monthly_credits=cr, features=feats, sort=i))
        else:  # add feature flags introduced by newer versions without touching what an admin changed
            missing = {k: v for k, v in feats.items() if k not in row.features}
            if missing:
                row.features = {**row.features, **missing}
    db.commit()


def _ensure_user(db: Session, email: str, name: str, admin: bool, pw: str | None) -> str | None:
    if db.scalar(select(User.id).where(User.email == email)):
        return None
    pw = pw or secrets.token_urlsafe(9)
    u = User(email=email, name=name, password_hash=hash_password(pw), is_admin=admin, email_verified=True)
    db.add(u)
    db.commit()
    credits.grant(db, u.id, 1_000_000 if get_settings().app_mode == "self_host" else 100, "seed grant")
    return pw


def seed_demo() -> dict:
    out = {}
    with SessionLocal() as db:
        ensure_reference_data(db)
        for email, name, admin in [("admin@clue.local", "Admin", True), ("demo@clue.local", "Demo Creator", False)]:
            pw = _ensure_user(db, email, name, admin, None)
            out[email] = pw or "(already exists; password unchanged)"
    return out


if __name__ == "__main__":
    import json

    res = seed_demo()
    f = get_settings().storage_dir / "demo-credentials.json"
    known = json.loads(f.read_text()) if f.exists() else {}
    known.update({k: v for k, v in res.items() if not v.startswith("(")})
    f.write_text(json.dumps(known, indent=2))
    for email in res:
        print(f"{email} / {known.get(email, '(unknown)')}")
